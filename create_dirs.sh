if [[ $# -ne 1 ]]; then
    echo "Illegal number of parameters. Course name not provided."
    exit 2
fi

course_id="$1"

mkdir -p mnt/my-org/exchange
chown -R root:root mnt/my-org
chmod 0755 mnt/my-org
chmod 0777 mnt/my-org/exchange

mkdir -p mnt/my-org/home/grader-"$course_id"/.jupyter
mkdir -p mnt/my-org/home/grader-"$course_id"/"$course_id"
chown -R 10001:100 mnt/my-org/home/grader-"$course_id"
