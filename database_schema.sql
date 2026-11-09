-- MedPredict initial MySQL schema (MySQL 8 / MariaDB compatible)
-- Import this file into the empty database created by your PHP hosting provider.
-- Review this schema against your final application requirements before real use.

CREATE TABLE IF NOT EXISTS users (
  user_id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(150) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  date_of_birth DATE NOT NULL,
  sex TINYINT NOT NULL COMMENT '0=female, 1=male, matching current PHP form encoding',
  phone VARCHAR(30) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS health_questionnaires (
  questionnaire_id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNSIGNED NOT NULL UNIQUE,
  smoking_status VARCHAR(30) NOT NULL,
  alcohol_consumption VARCHAR(30) NOT NULL,
  dm TINYINT(1) NOT NULL DEFAULT 0,
  htn TINYINT(1) NOT NULL DEFAULT 0,
  family_history_heart_disease TINYINT(1) NOT NULL DEFAULT 0,
  height_ft DECIMAL(5,2) DEFAULT NULL,
  weight_kg DECIMAL(6,2) DEFAULT NULL,
  bmi DECIMAL(6,2) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_questionnaire_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS blood_reports (
  report_id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_blood_reports_user (user_id),
  CONSTRAINT fk_blood_report_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS blood_test_results (
  result_id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  report_id INT UNSIGNED NOT NULL,
  age INT DEFAULT NULL,
  gender TINYINT DEFAULT NULL,
  alb DECIMAL(12,4) DEFAULT NULL,
  alkphos DECIMAL(12,4) DEFAULT NULL,
  sgpt DECIMAL(12,4) DEFAULT NULL,
  sgot DECIMAL(12,4) DEFAULT NULL,
  tb DECIMAL(12,4) DEFAULT NULL,
  tp DECIMAL(12,4) DEFAULT NULL,
  hba1c DECIMAL(12,4) DEFAULT NULL,
  glucose_level DECIMAL(12,4) DEFAULT NULL,
  sg DECIMAL(12,4) DEFAULT NULL,
  al DECIMAL(12,4) DEFAULT NULL,
  bu DECIMAL(12,4) DEFAULT NULL,
  sc DECIMAL(12,4) DEFAULT NULL,
  sod DECIMAL(12,4) DEFAULT NULL,
  pot DECIMAL(12,4) DEFAULT NULL,
  hemo DECIMAL(12,4) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_blood_test_report (report_id),
  CONSTRAINT fk_blood_test_report FOREIGN KEY (report_id) REFERENCES blood_reports(report_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS blood_test_observations (
  observation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  result_id INT UNSIGNED NOT NULL,
  test_name VARCHAR(64) NOT NULL,
  result_value TEXT NOT NULL,
  INDEX idx_observations_result (result_id),
  CONSTRAINT fk_observation_result FOREIGN KEY (result_id) REFERENCES blood_test_results(result_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS prediction_results (
  prediction_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  result_id INT UNSIGNED NOT NULL,
  model_name VARCHAR(32) NOT NULL,
  predicted_class VARCHAR(16) NOT NULL,
  class_probabilities LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY unique_result_model (result_id, model_name),
  INDEX idx_prediction_result (result_id),
  CONSTRAINT fk_prediction_result FOREIGN KEY (result_id) REFERENCES blood_test_results(result_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admin_accounts (
  admin_id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
