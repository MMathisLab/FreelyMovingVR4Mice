#!/bin/bash

source utils.sh

log "Start backup procedure!"

databases=$(mysql $group$s1_prefix $ssl -e "SHOW DATABASES;" |
	grep -Ev "(Database|information_schema|performance_schema|mysql|sys|base|base_analysis|dlc)")

log "Detected databases to backup: $databases"

databases=(dlc)

#for db in "${databases[@]}"; do
for db in $databases; do

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

 cmd="mysqldump $group$s1_prefix $ssl --ignore-table='vr4mice'.'~log'--ignore-table='dlc'.'~log' \
             	--single-transaction --quick --max_allowed_packet=512M --skip-add-drop-table --insert-ignore "$db" \
                | sed 's/CREATE TABLE/CREATE TABLE IF NOT EXISTS/g' \
 		            | sed 's/INSERT INTO/INSERT IGNORE INTO/g' \
		            | mysql  $group$aws_prefix $db"
    
 #execute_command "$cmd" "$msg"

 # Step 1: Dump the database to an intermediate file and modify it
 cmd1="mysqldump $group$s1_prefix $ssl --ignore-table='vr4mice'.'~log' --ignore-table='dlc'.'~log' \
		--single-transaction --quick --max_allowed_packet=512M --skip-add-drop-table --insert-ignore \"$db\" \
		> $db.sql && \
		sed -i 's/CREATE TABLE/CREATE TABLE IF NOT EXISTS/g' $db.sql && \
		sed -i 's/INSERT INTO/INSERT IGNORE INTO/g' $db.sql"

 #execute_command "$cmd1" "$msg"

 # Step 2: Import the modified SQL dump into MySQL and clean up the file
 cmd2="mysql $group$aws_prefix --max_allowed_packet=1G \"$db\" < $db.sql "
 
 #execute_command "$cmd2" "$msg"

tables=$(mysql $group$s1_prefix $ssl -e "SHOW TABLES IN $db;" -s --skip-column-names)

	# Loop through each table
	for table in $tables; do
	    
	    msg="Dumping and importing database: $db, table $table"
	    
	    cmd3="mysqldump $group$s1_prefix $ssl --ignore-table='$db'.'~log' --max_allowed_packet=1G $db $table \
			| sed 's/CREATE TABLE/CREATE TABLE IF NOT EXISTS/g' \
				    | sed 's/INSERT INTO/INSERT IGNORE INTO/g' \
				    | mysql $group$aws_prefix $db --max_allowed_packet=1G"
	    
	    execute_command "$cmd3" "$msg"
	    
	    echo "All chunks processed successfully."
	done
done
