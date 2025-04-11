-- phpMyAdmin SQL Dump
-- Create and use the database
CREATE DATABASE IF NOT EXISTS `chatbot_db`;
USE `chatbot_db`;

-- Drop existing tables if they exist
DROP TABLE IF EXISTS `login_history`;
DROP TABLE IF EXISTS `users`;

-- Create users table with updated structure
CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(80) UNIQUE NOT NULL,
    `email` VARCHAR(120) UNIQUE NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    `reset_token` VARCHAR(100),
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Create login_history table
CREATE TABLE `login_history` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT,
    `username` VARCHAR(80),
    `login_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert sample users with hashed passwords and emails
INSERT INTO `users` (`username`, `email`, `password`) VALUES
('admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewFX.gtkn.PaPQO2'),  -- Password: admin123
('test', 'test@example.com', '$2b$12$8NKxJWJD.a/w8.4c8TvCdu/P.JK1Dz.5Df9KNPPUQEiwlKqfFWGYe'),   -- Password: test123
('user1', 'user1@example.com', '$2b$12$B5uE2n0PRgz8N8C2x8LWs.XWRV8Ej.6Qz5gBwcEZJX9HnVKnq3vyq'); -- Password: password123

-- Add indexes for better performance
ALTER TABLE `users` ADD INDEX `idx_username` (`username`);
ALTER TABLE `users` ADD INDEX `idx_email` (`email`);
ALTER TABLE `login_history` ADD INDEX `idx_user_id` (`user_id`);
ALTER TABLE `login_history` ADD INDEX `idx_login_time` (`login_time`);