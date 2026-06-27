import asyncio
import time
import os
import shutil
from easycord.database import SQLiteDatabase

async def db_writer(db, guild_id, records_to_write):
    """Writes multiple records to a specific guild to simulate burst."""
    for i in range(records_to_write):
        await db.set(
            guild_id=guild_id,
            key=f"stress_key_{i}",
            value={"data": f"payload_{i}", "timestamp": time.time()}
        )

async def main():
    print("--- Database Stress Test ---")
    db_path = "stress_test.db"
    
    # Cleanup previous run
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = SQLiteDatabase(path=db_path)
    await db.ensure_schema()
    
    num_guilds = 100
    writes_per_guild = 50
    total_writes = num_guilds * writes_per_guild
    
    print(f"Target: {total_writes} total writes ({num_guilds} guilds x {writes_per_guild} writes/guild)")
    
    start_time = time.time()
    
    # Launch concurrent writers
    tasks = []
    for guild_id in range(1, num_guilds + 1):
        tasks.append(asyncio.create_task(db_writer(db, guild_id, writes_per_guild)))
        
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    elapsed = end_time - start_time
    writes_per_sec = total_writes / elapsed
    
    print(f"\nResults:")
    print(f"Total Time: {elapsed:.2f} seconds")
    print(f"Throughput: {writes_per_sec:.2f} writes/second")
    
    # Verify records
    print("\nVerifying records...")
    verified = 0
    for guild_id in range(1, num_guilds + 1):
        for i in range(writes_per_guild):
            record = await db.get(guild_id, f"stress_key_{i}")
            if record and record["data"] == f"payload_{i}":
                verified += 1
                
    print(f"Verified {verified}/{total_writes} records.")
    if verified == total_writes:
        print("PASS: All records were written and verified successfully.")
    else:
        print("FAIL: Data loss detected during stress test.")
        
    await db.close()
    
    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    asyncio.run(main())
