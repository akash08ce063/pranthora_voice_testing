-- Migration: Add new columns and constraints for enhanced test case and result management
-- Run this SQL in your Supabase SQL editor or database console

-- Add new columns to test_cases table
ALTER TABLE test_cases
ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 1 CHECK (attempts > 0),
ADD COLUMN IF NOT EXISTS default_concurrent_calls INTEGER DEFAULT 1 CHECK (default_concurrent_calls > 0);

-- Add test_suite_id foreign key to test_case_results table
ALTER TABLE test_case_results
ADD COLUMN IF NOT EXISTS test_suite_id UUID REFERENCES test_suites(id) ON DELETE CASCADE;

-- Create index for the new foreign key
CREATE INDEX IF NOT EXISTS idx_test_case_results_test_suite_id ON test_case_results(test_suite_id);

-- Ensure all tables have proper user_id references (for Supabase auth compatibility)
-- Note: These should already exist, but let's verify/update them

-- Update any existing test_run_history records that might not have user_id
-- (This assumes you have a way to map existing records to users)

-- Add comments for documentation
COMMENT ON COLUMN test_cases.attempts IS 'Number of times this test case should retry on failure';
COMMENT ON COLUMN test_cases.default_concurrent_calls IS 'Default number of concurrent calls for this test case';
COMMENT ON COLUMN test_case_results.test_suite_id IS 'Reference to the test suite this result belongs to';
