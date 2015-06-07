#!/bin/bash
#TMS=$(date +"%Y-%m-%d %H:%M:%S")
#echo "$TMS $1 $2 $3 $4 $5 $6 $7" >> /tmp/pd.log

if [ $1 == umount ]; then
    ACTION=$1
    UUID=$2
else
    UUID=$1
    ACTION=$2
fi

DEVICE=$3	# device name like my-name__SEP__user
NAME=$4
SIZE=$5
AWS_ACCESS_KEY_ID=$6
AWS_SECRET_ACCESS_KEY=$7

IID=$(curl -s --connect-timeout 1 http://169.254.169.254/latest/meta-data/instance-id)
AV_ZONE=""
REGION=""
FREE_CHAR=""
if [ -n "$IID" ];then
    AV_ZONE=$(curl -s connect-timeout 1 http://169.254.169.254/latest/meta-data/placement/availability-zone)
    REGION=$(echo $AV_ZONE|sed 's/\([0-9][0-9]*\)[a-z]*$/\1/')
fi
MP="/var/lib/kubelet/pods/$UUID/volumes/kubernetes.io~scriptable-disk/$NAME"

if [ $USER != root ];then
    echo "Superuser privileges required"
    exit 0
fi

function mkdir_if_missing {
    if [ ! -d "$MP" ];then
        mkdir -p "$MP"
    fi
}

function get_next {
    ARRAY=($(ls -1 /dev/xvd*|awk -F '' '/xvd/ {print $9}'|sort))
    NEXT=$(($(printf "%d" "'${ARRAY[-1]}")+1))
    if [ "$NEXT" -gt 122 ];then
        exit 1
    fi
    FREE_CHAR=$(awk "BEGIN{printf \"%c\", $NEXT}")
}


function remove_volume {
    AWS_ACCESS_KEY_ID=$2
    AWS_SECRET_ACCESS_KEY=$3
    VOLNAME=$4
    export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
    aws ec2 delete-volume --volume-id=$VOLNAME --region=$REGION
    unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
}

function create_map_and_mount {
    mkdir_if_missing
    if [ -z "$IID" ];then    # not aws
        SIZE_MB=$((1024*$SIZE))
        rbd create $DEVICE --size=$SIZE_MB
        DEVICE=$(rbd map $DEVICE)
        mkfs.ext4 $DEVICE
        mount "$DEVICE" "$MP"
    else # aws
        get_next
        if [ -z "$FREE_CHAR" ];then
            exit 1
        fi
        NEXT_DEV="xvd$FREE_CHAR"
        if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "AWS_SECRET_ACCESS_KEY" ];then
            export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
            VOL=$(aws ec2 create-volume --size=$SIZE --region=$REGION --availability-zone=$AV_ZONE | jq -r  '.VolumeId')
            aws ec2 create-tags --resources=$VOL --region=$REGION --tags Key=Name,Value=$DEVICE
            aws ec2 attach-volume --volume-id=$VOL --instance-id=$IID --device=$NEXT_DEV --region=$REGION
            while [ $? -ne 0 ];do
                sleep 1
                aws ec2 attach-volume --volume-id=$VOL --instance-id=$IID --device=$NEXT_DEV --region=$REGION
            done
            mkfs.ext4 "/dev/$NEXT_DEV"
            while [ $? -ne 0 ];do
                sleep 2
                mkfs.ext4 "/dev/$NEXT_DEV"
            done
            mount "/dev/$NEXT_DEV" "$MP"
            unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
        fi
    fi
}

function map_and_mount {
    if [ -z "$IID" ];then
        rbd showmapped|awk "NR>1{if(\$3==\"$DEVICE\"){exit 1}}"
        if [ $? -ne 0 ];then
            exit 1
        fi
        mkdir_if_missing
        DEVICE=$(rbd map $DEVICE)
        mount "$DEVICE" "$MP"
    else
        RV=$(aws ec2 describe-volumes --region=$REGION --filters "Name=tag-key,Values=Name" "Name=tag-value,Values=$DEVICE")
        RES=$(echo $RV | jq -r ".Volumes[0].State")
        if [ $RES != available ];then
            exit 1
        fi
        mkdir_if_missing
        get_next
        if [ -z "$FREE_CHAR" ];then
            exit 1
        fi
        NEXT_DEV="xvd$FREE_CHAR"
        VOL=$(echo $RV | jq -r ".Volumes[0].VolumeId")
        aws ec2 attach-volume --volume-id=$VOL --instance-id=$IID --device=$NEXT_DEV --region=$REGION
        while [ $? -ne 0 ];do
            sleep 1
            aws ec2 attach-volume --volume-id=$VOL --instance-id=$IID --device=$NEXT_DEV --region=$REGION
        done
        mount "/dev/$NEXT_DEV" "$MP"
        while [ $? -ne 0 ];do
            sleep 1
            mount "/dev/$NEXT_DEV" "$MP"
        done
    fi
}

function lookup {
    if [ -z "$IID" ];then
        LIST=$(rbd ls)
        if [ -z "$LIST" ];then
            return 0
        else
            while read -r LINE; do
                if [ $LINE == $DEVICE ];then
                    return 1
                fi
            done <<< "$LIST"
            return 0
        fi
    else
        RV=$(aws ec2 describe-volumes --region=$REGION --filters "Name=tag-key,Values=Name" "Name=tag-value,Values=$DEVICE")
        RES=$(echo $RV | jq -r ".Volumes[0].VolumeId")
	if [ $RES == null ];then
            return 0
        fi
        return 1
    fi
}

function make_unmount {
    DRIVES=$(mount | awk "/$UUID/ {print \$1}")
    if [ -z "$DRIVES" ];then
        exit 0
    fi

    while read -r DRIVE;do
        umount $DRIVE
        if [ -z "$IID" ];then
            rbd unmap $DRIVE
        else
           STRIPPED_DRIVE=$(echo $DRIVE | sed 's/\/dev\/\(.*\)$/\1/')
           RV=$(aws ec2 describe-volumes --region=$REGION --filters "Name=attachment.device,Values=$STRIPPED_DRIVE")
           VOL=$(echo $RV | jq -r ".Volumes[0].VolumeId")
           aws ec2 detach-volume --region=$REGION --volume-id=$VOL
        fi
    done <<< "$DRIVES"
}

if [ $ACTION == "create" ];then
    lookup
    if [ $? -eq 0 ];then
        create_map_and_mount
    else
        exit 1
    fi
elif [ $ACTION == "mount" ];then
    lookup
    if [ $? -eq 0 ];then
        exit 1
    else
        map_and_mount
    fi
elif [ $ACTION == "umount" ];then
    make_unmount
fi
