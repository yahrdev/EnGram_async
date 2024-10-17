"""the file for tests configuration. To run tests: pytest -v  tests/"""

from typing import AsyncGenerator
import pytest
from httpx import AsyncClient, ASGITransport
from api.models import Questions
from api.app import create_app, setup_cache
from config import settings
from sqlalchemy import update, select
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession,  create_async_engine, async_sessionmaker



app = create_app()

engine_test = create_async_engine(settings.DB_URL)
async_session_maker = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False) 


@pytest.fixture(scope="session")
def event_loop(request):

    """Create an instance of the default event loop for each session."""

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.run_until_complete(loop.shutdown_asyncgens()) 
    loop.close()



@pytest.fixture(autouse=True)
async def prepare_database():
    """we do not create a new db everytime but we clean datetime_shown"""

    if settings.MODE != "TEST":
        pytest.fail("An error occurred while preparing the db: the database is not for testing")
    
    await _update_tests()
    yield




# @pytest.fixture(autouse=True, scope="module")
# async def create_database():
#     """the database will be cleared after each test"""
#     assert settings.MODE == "TEST"
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#     yield


@pytest.fixture(autouse=True)
async def init_test_cache(event_loop):
    """the fixture for cache init"""
    
    try:
        cache_listener = setup_cache(app)
        cache_listener.start_cache_listener()
        
        yield cache_listener
    except Exception as e:
        pytest.fail(f"An error occurred while preparing the cache: {e}")
    finally:
        try:
            await cache_listener.on_stop_app()
            cache_listener.stop_cache_listener()
        except Exception as e:
            pytest.fail(f"An error occurred while stopping the cache listener: {e}")
            

@pytest.fixture()
async def ac() -> AsyncGenerator[AsyncClient, None]:
    """Pytest fixture to provide an AsyncClient for testing the ASGI app."""
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as ac:      
        yield ac


@pytest.fixture(scope="module")
async def select_level() -> tuple[str, int, dict]:
    """this fixture checks the testing db and gathers information about existing questions for every level"""
    try:
        Questions_Count = await _get_tests_from_db()
        Selected_Level = max(Questions_Count, key=Questions_Count.get)
        if Questions_Count[Selected_Level] > 50:  #<=50 questions is enough for testing
            return Selected_Level, 50, Questions_Count
        else:
            return Selected_Level, Questions_Count[Selected_Level], Questions_Count
    except Exception as e:
            pytest.fail(f"An error occurred while selecting the level: {e}")
    


@pytest.fixture(scope="module")
def level(select_level) -> str:
    """selected testing level for all tests"""
    return select_level[0]


@pytest.fixture(scope="module")
def questions_number_to_test(select_level) -> int:
    """the max number of questions to use in test_consistency"""
    return select_level[1]

@pytest.fixture(scope="module")
def questions_count_dict(select_level) -> dict:
    """the dict {Level: number of tests in db}"""
    return select_level[2]

    

async def _get_tests_from_db() -> dict:
    """we check existing questions in the testing db and create a dict like {level: number of tests}"""
    try:
        async with async_session_maker() as session:
            Stmt = select(Questions)
            Result = await session.execute(Stmt)
            
        Questions_Count = {}
        
        for (q,) in Result.fetchall():
            q: Questions
            if q.level.value in Questions_Count:
                Questions_Count[q.level.value] += 1
            else:
                Questions_Count[q.level.value] = 1
        if not Questions_Count:
            pytest.fail(f"An error occurred while getting data from the db: There are no data in db")
        return Questions_Count
    except Exception as e:
        pytest.fail(f"An error occurred while getting data from the db: {e}")




async def check_datetime_in_db(for_level) -> int:
    """get number of updated questions in db"""
    try:
        async with async_session_maker() as session:
            
            Stmt = select(Questions).where(Questions.level == for_level)
            Result = await session.execute(Stmt)
            
        i = 0
        for (q,) in Result.fetchall():
            q: Questions
            if q.datetime_shown:
                i += 1
        return i

    except Exception as e:
        pytest.fail(f"An error occurred while getting data from the db for checking: {e}")

        



async def _update_tests():
    """for preparing the testing db"""
    try:
        async with async_session_maker() as session:
            statement = update(Questions).values(datetime_shown = None)
            await session.execute(statement)
            await session.commit()
    except Exception as e:
        pytest.fail(f"An error occurred while preparing the db: {e}")
