#!/bin/bash

source utils.sh

log "Start backup procedure!"
#Get a list of all databases from the source host
databases=$(mysql $group$s1_prefix $ssl -e "SHOW DATABASES;" |
	grep -Ev "(Database|information_schema|performance_schema|mysql|sys)")

databases=(dlc)
log "Detected databases to backup: $databases"

# Loop through each database and perform mysqldump on the source host
for db in "${databases[@]}"; do
#for db in $databases; do
	# Check if the database already exists
	if mysql $group$aws_prefix $ssl -e "USE $db;" >/dev/null 2>&1; then
		log "Database $db already exists. Skipping creation."
	else
		# If the database does not exist, create it
		cmd="mysqladmin $group$aws_prefix $ssl create $db"
		msg="Create new database on AWS: $db"
		execute_command "$cmd" "$msg"
	fi

	msg="Dumping and importing database: $db"
        cmd="mysqldump $group$s1_prefix $ssl --ignore-table='vr4mice'.'~log' --ignore-table='dlc'.'~log'
             	--max-allowed-packet=512M  --skip-add-drop-table --insert-ignore "$db" \
                | sed 's/CREATE TABLE/CREATE TABLE IF NOT EXISTS/g' \
 		| sed 's/INSERT INTO/INSERT IGNORE INTO/g'> $db.sql
	#\
	#	| mysql  $group$aws_prefix $db"
       	
	cmd="mysql $group$aws_prefix $db < $db.sql"
	execute_command "$cmd" "$msg"
	
	#execute_command "mysqldump $group$s1_prefix $ssl --single-transaction --quick --max-allowed-packet=1024M --column-statistics=0 $db \
	#	| mysql $group$aws_prefix $db" "Dumping and importing database: $db"
done

