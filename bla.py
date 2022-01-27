import asyncio


async def a():
    print("first")
    await asyncio.sleep(1)
    print("second")
    return "return"


async def b():
    a1 = asyncio.create_task(a())
    a2 = asyncio.create_task(a())
    all_a = [asyncio.create_task(a()) for _ in range(4)]
    await asyncio.sleep(3)
    print(await a1)
    print(await a2)
    print(await asyncio.gather(*all_a))


if __name__ == "__main__":
    asyncio.run(b())
