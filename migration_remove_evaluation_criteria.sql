-- Migration: Remove evaluation_criteria column and add temperature column to user_agents table
-- Run this SQL in your Supabase SQL editor or database console

-- Add temperature column
ALTER TABLE user_agents
ADD COLUMN IF NOT EXISTS temperature DECIMAL(3,2) DEFAULT 0.7 CHECK (temperature >= 0.0 AND temperature <= 2.0);

-- Drop evaluation_criteria column (be careful with data loss!)
ALTER TABLE user_agents
DROP COLUMN IF EXISTS evaluation_criteria;

-- Add comment for the new column
COMMENT ON COLUMN user_agents.temperature IS 'Temperature setting for the AI model (0.0 to 2.0)';
