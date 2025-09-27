CREATE DATABASE syslogs;
USE syslogs;

CREATE TABLE stats (
  id INT AUTO_INCREMENT PRIMARY KEY,
  timestamp DATETIME,
  cpu_usage FLOAT,
  memory_usage FLOAT
);
