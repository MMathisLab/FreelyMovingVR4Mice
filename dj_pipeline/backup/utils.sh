#!bin/bash

s1_prefix="-vr4mice"
aws_prefix="-aws_vr4mice"
ssl="--ssl-mode=disabled"
group="--defaults-group-suffix="

logs="./logs"
log_file=$logs/log.log
error_file=$logs/error.log
err=""

# Create log directory if it doesn't exist
if [ ! -d "$logs" ]; then
	mkdir -p "$logs"
fi

log() {
	msg="[$(date +'%Y-%m-%d %H:%M:%S')] $1"
	echo $msg
	echo $msg >>"$log_file"
}

error_exit() {
	msg="[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1"
	echo $msg
	echo $msg >>"$error_file"
	exit 1
}

execute_command() {
	local command=$1
	local message=$2
	log "$message"
	eval $command >>"$log_file"
	local return_code=$?
	if [ $return_code -ne 0 ]; then
		log "Command exited with return code: $return_code"
		error_exit "executing command: $command"
	else
		log "[OK]"
	fi
}
