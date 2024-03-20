CREATE USER 'user'@'%' IDENTIFIED BY 'pwd';

GRANT SELECT ON `%vr4mice%`.* TO 'user'@'%';
GRANT SELECT ON `exp`.* TO 'user'@'%';
GRANT SELECT ON `mice`.* TO 'user'@'%';
GRANT SELECT, INSERT, UPDATE ON `mice`.`#strain` TO 'user'@'%';

