import unittest
import mock
from ..users import UserCollection, User, APIError, POD_STATUSES
from ...testutils.testcases import DBTestCase


@mock.patch.object(User, 'logout')
@mock.patch.object(UserCollection, '_suspend_user')
@mock.patch.object(UserCollection, '_unsuspend_user')
class TestUserUpdate(DBTestCase):
    def setUp(self):
        self.user, _ = self.fixtures.user_fixtures()

    def test_suspend(self, unsuspend_mock, suspend_mock, logout_mock):
        """Suspend/unsuspend."""
        UserCollection().update(self.user.id, {'suspended': True})
        suspend_mock.assert_called_once_with(self.user)
        # second "suspend" does nothing
        UserCollection().update(self.user.id, {'suspended': True})
        self.assertEqual(suspend_mock.call_count, 1)

        UserCollection().update(self.user.id, {'suspended': False})
        unsuspend_mock.assert_called_once_with(self.user)
        # second "unsuspend" does nothing
        UserCollection().update(self.user.id, {'suspended': False})
        self.assertEqual(unsuspend_mock.call_count, 1)

    def test_lock(self, unsuspend_mock, suspend_mock, logout_mock):
        """Lock/unlock."""
        UserCollection().update(self.user.id, {'active': False})
        suspend_mock.assert_called_once_with(self.user)
        logout_mock.assert_called_once_with(commit=False)
        # second "lock" does nothing
        UserCollection().update(self.user.id, {'active': False})
        self.assertEqual(suspend_mock.call_count, 1)
        self.assertEqual(logout_mock.call_count, 1)

        UserCollection().update(self.user.id, {'active': True})
        unsuspend_mock.assert_called_once_with(self.user)
        # second "unlcok" does nothing
        UserCollection().update(self.user.id, {'active': True})
        self.assertEqual(unsuspend_mock.call_count, 1)

    def test_suspend_locked(self, unsuspend_mock, suspend_mock, logout_mock):
        """If user is "locked" already, "suspend" and "unsuspend" will change nothing."""
        UserCollection().update(self.user.id, {'active': False})
        suspend_mock.reset_mock()
        unsuspend_mock.reset_mock()

        UserCollection().update(self.user.id, {'suspended': True})
        self.assertFalse(suspend_mock.called)
        UserCollection().update(self.user.id, {'suspended': False})
        self.assertFalse(unsuspend_mock.called)

    def test_lock_suspended(self, unsuspend_mock, suspend_mock, logout_mock):
        """
        If user is "suspended" already, "lock" will only logout the user and
        "unlock" will do nothing.
        """
        UserCollection().update(self.user.id, {'suspended': True})
        suspend_mock.reset_mock()
        unsuspend_mock.reset_mock()

        UserCollection().update(self.user.id, {'active': False})
        self.assertFalse(suspend_mock.called)
        logout_mock.assert_called_once_with(commit=False)
        UserCollection().update(self.user.id, {'active': True})
        self.assertFalse(unsuspend_mock.called)

    def test_unsuspend_error(self, unsuspend_mock, suspend_mock, logout_mock):
        """If error was rised during unsuspend, all changes must be rolled back."""
        UserCollection().update(self.user.id, {'suspended': True})

        class ReturnIPError(APIError):
            message = "Couldn't return ip: pool is empty"
        unsuspend_mock.side_effect = ReturnIPError()

        with self.assertRaises(ReturnIPError):
            UserCollection().update(self.user.id, {'suspended': False})
        unsuspend_mock.assert_called_once_with(self.user)
        self.assertTrue(UserCollection().get(self.user.id)['suspended'])

        unsuspend_mock.reset_mock()
        unsuspend_mock.side_effect = TypeError('Some internal error')

        try:
            UserCollection().update(self.user.id, {'suspended': False})
        except APIError as e:
            self.assertEqual(e.status_code, 500)
            self.assertEqual(e.type, 'UserUpdateError')
        else:
            self.fail('UserUpdateError was not rised')
        unsuspend_mock.assert_called_once_with(self.user)
        self.assertTrue(UserCollection().get(self.user.id)['suspended'])


class TestSuspendHelpers(DBTestCase):
    def setUp(self):
        self.user, _ = self.fixtures.user_fixtures()

        patcher = mock.patch('kubedock.kapi.users.PodCollection')
        self.addCleanup(patcher.stop)
        self.PodCollectionMock = patcher.start()
        self.PodCollectionMock.return_value.get.return_value = [
            {'status': POD_STATUSES.stopped, 'id': 'stopped-pod'},
            {'status': POD_STATUSES.running, 'id': 'running-pod'},
            {'status': POD_STATUSES.pending, 'id': 'pending-pod'},
        ]

    def test_suspend(self):
        """
        Method kubedock.kapi.users.UserCollection._suspend_user must stop all
        user's pods and free IPs.
        """
        UserCollection()._suspend_user(self.user)
        self.PodCollectionMock.assert_called_once_with(self.user)
        self.PodCollectionMock().get.assert_called_once_with(as_json=False)
        self.PodCollectionMock().update.assert_has_calls([
            mock.call('running-pod', {'command': 'stop'}),
            mock.call('pending-pod', {'command': 'stop'}),
        ])
        self.PodCollectionMock()._remove_public_ip.assert_has_calls([
            mock.call(pod_id='stopped-pod'),
            mock.call(pod_id='running-pod'),
            mock.call(pod_id='pending-pod'),
        ])

    def test_unsuspend(self):
        """
        Method kubedock.kapi.users.UserCollection._suspend_user must return all
        IPs to user's pods.
        """
        UserCollection()._unsuspend_user(self.user)
        self.PodCollectionMock.assert_called_once_with(self.user)
        self.PodCollectionMock().get.assert_called_once_with(as_json=False)
        self.PodCollectionMock()._return_public_ip.assert_has_calls([
            mock.call('stopped-pod'),
            mock.call('running-pod'),
            mock.call('pending-pod')
        ])


if __name__ == '__main__':
    unittest.main()
