if [[ $# -ne 2 ]]; then
    echo "Illegal number of parameters. Course name and grader name not provided."
    exit 2
fi


course_id="$1"
grader_name="$2"

mkdir -p mnt/my-org/home/"$grader_name"/.jupyter/
cp mnt/my-org/home/grader-"$course_id"/"$course_id"/nbgrader_config.py mnt/my-org/home/$grader_name/.jupyter/
chown -R 1000:100 mnt/my-org/home/"$grader_name"
