import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def reset():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.seraph_ai_defense
    email = "buntbyron@gmail.com"
    new_password = "Byron2026!"
    hashed = pwd_context.hash(new_password)
    
    result = await db.users.update_one(
        {"email": email},
        {"$set": {"password": hashed}}
    )
    if result.modified_count > 0:
        print(f"SUCCESS: Password reset for {email}")
    else:
        print(f"FAILED: User {email} not found or no change")

if __name__ == '__main__':
    asyncio.run(reset())
