CREATE DATABASE IF NOT EXISTS syslogs;
USE syslogs;

CREATE TABLE IF NOT EXISTS stats (
  id INT AUTO_INCREMENT PRIMARY KEY,
  timestamp DATETIME,
  cpu_usage FLOAT,
  memory_usage FLOAT,
  host VARCHAR(128)
);
