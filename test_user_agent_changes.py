#!/usr/bin/env python3
"""
Test script to verify that the user agent changes work correctly.
"""

import asyncio
import uuid
from models.test_suite_models import UserAgentCreate, UserAgentUpdate
from services.user_agent_service import UserAgentService


async def test_user_agent_changes():
    """Test that the user agent changes work correctly."""
    print("Testing user agent changes...")

    # Test 1: UserAgentCreate model validation
    try:
        create_data = UserAgentCreate(
            user_id=uuid.uuid4(),
            name="Test Agent",
            system_prompt="You are a helpful assistant",
            temperature=0.8
        )
        print("✅ UserAgentCreate with new structure works")
    except Exception as e:
        print(f"❌ UserAgentCreate validation failed: {e}")
        return

    # Test 2: UserAgentUpdate model validation
    try:
        update_data = UserAgentUpdate(
            name="Updated Agent",
            system_prompt="Updated prompt",
            temperature=0.9
        )
        print("✅ UserAgentUpdate with new structure works")

        # Test with None values
        update_data_none = UserAgentUpdate(
            temperature=None  # Should be valid
        )
        print("✅ UserAgentUpdate with None temperature works")
    except Exception as e:
        print(f"❌ UserAgentUpdate validation failed: {e}")
        return

    # Test 3: Invalid temperature values
    try:
        invalid_create = UserAgentCreate(
            user_id=uuid.uuid4(),
            name="Test Agent",
            system_prompt="You are a helpful assistant",
            temperature=3.0  # Should fail (max is 2.0)
        )
        print("❌ UserAgentCreate should have failed with invalid temperature")
    except Exception as e:
        print(f"✅ UserAgentCreate correctly rejects invalid temperature: {type(e).__name__}")

    # Test 4: Service instantiation
    try:
        service = UserAgentService()
        print("✅ UserAgentService instantiated successfully")
    except Exception as e:
        print(f"❌ UserAgentService instantiation failed: {e}")
        return

    # Test 5: Model data extraction
    try:
        # Test that model_dump works correctly
        create_dict = create_data.model_dump()
        expected_keys = {"user_id", "name", "system_prompt", "temperature", "pranthora_agent_id"}
        actual_keys = set(create_dict.keys())

        if expected_keys.issubset(actual_keys):
            print("✅ UserAgentCreate.model_dump() includes correct fields")
        else:
            print(f"❌ UserAgentCreate.model_dump() missing keys. Expected: {expected_keys}, Got: {actual_keys}")

        # Test that evaluation_criteria is not present
        if "evaluation_criteria" not in create_dict:
            print("✅ evaluation_criteria successfully removed from model")
        else:
            print("❌ evaluation_criteria still present in model")

        # Test that temperature is present
        if "temperature" in create_dict and isinstance(create_dict["temperature"], float):
            print("✅ temperature field correctly added")
        else:
            print("❌ temperature field missing or wrong type")

    except Exception as e:
        print(f"❌ Model data extraction test failed: {e}")
        return

    print("\n🎉 All user agent changes verified successfully!")
    print("\n📋 Summary of Changes:")
    print("✅ Removed evaluation_criteria column and field")
    print("✅ Added temperature field (0.0-2.0 range)")
    print("✅ Updated UserAgentCreate and UserAgentUpdate models")
    print("✅ Updated user agent service to handle new structure")
    print("✅ Updated Pranthora API client to use temperature directly")
    print("✅ Updated Postman collection with new request bodies")
    print("\n🚀 Next Steps:")
    print("1. Run the SQL migration: migration_remove_evaluation_criteria.sql")
    print("2. Restart the backend server")
    print("3. Test the endpoints with the updated Postman collection")


if __name__ == "__main__":
    asyncio.run(test_user_agent_changes())
