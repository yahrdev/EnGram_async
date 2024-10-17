"""The functions for cache managing"""

from config import settings
from typing import List, Union
from schemas import CachedTests
from models import Questions, get_async_session
from quart import Quart
from sqlalchemy import update
import aioredis
import json
import asyncio
from datetime import datetime
from handlers import global_error_handler_async, global_error_handler_sync



"""In the following functions, CachedList has the following structure:
CachedList = [{
    "ID": int,
    "Question": str,
    "Options": [
        {
            "option_id": int,
            "option_text": str
        },
        ...
    ],
    "correct_option_id": int,
    "explanation": str,
    "datetime_shown": datetime,
    "shown": bool
}, {
    "ID": int, ...
},
...]
"""
@global_error_handler_sync
def initcache() -> aioredis.Redis:

    """init cache for the app"""


    redis_async = aioredis.from_url(
        f'redis://{settings.CACHE_REDIS_HOST}:{settings.CACHE_REDIS_PORT}/{settings.CACHE_REDIS_DB}'
    )
    return redis_async


    
class EngCache():

    """The class for cache processing"""

    def __init__(self, redis):
        self.redis = redis

    @global_error_handler_async
    async def set_key_with_ttl(self, key: str):

        """init expiration time for our keys"""

        await self.redis.expire(key, settings.CACHE_DEFAULT_TIMEOUT)
        
    @global_error_handler_async
    async def addtocache(self, Tests_list: List[dict], level):

        """adding data from database to cache"""
        ToCache = []
        for k in Tests_list:
            newcachedtest = CachedTests(**k)  #we use pydantic in order to avoide text in code
            if newcachedtest.datetime_shown != None:
                newcachedtest.datetime_shown = newcachedtest.datetime_shown.isoformat()  #from datetime to string because otherwise json.dumps(To Cache) will not work
            ToCache.append(newcachedtest.model_dump())
            await self.redis.set(level, json.dumps(ToCache))
            await self.set_key_with_ttl(level)


    @global_error_handler_async
    async def get_cached_test(self, level) -> Union[dict, None]:

        """retrieving data from cache"""

        GottenData = await self.redis.get(level)
        if GottenData:
            CachedList = json.loads(GottenData)
            Cached_Models = [CachedTests(**onetest) for onetest in CachedList]
            Filtered_Models = [m for m in Cached_Models if not m.shown] #just that tests which were not shown
            if Filtered_Models:
                return Filtered_Models[0].model_dump()
            
            else:    #the case when all tests in cache were already shown
                
                await send_cach_to_db(CachedList) #save data to db
                await self.redis.delete(level)  #clear cache
                return None
        else:
            return None

        

    @global_error_handler_async
    async def update_cached_tests(self, level, test_id, datetime_shown) -> bool:

        """updating Shown checkmark and datetime_shown in the cache"""

        GottenData = await self.redis.get(level)
        if GottenData:
            CachedList = json.loads(GottenData)
            i = 0
            for i, onetest in enumerate(CachedList):
                testclass = CachedTests(**onetest)
                if testclass.ID == test_id:   #Find the test with the required ID
                    testclass.datetime_shown = datetime_shown
                    testclass.shown = True
                    CachedList[i] = testclass.model_dump()
                    await self.redis.set(level, json.dumps(CachedList))
                    return True, ''
                i += 1
        return False
        
    
class CacheListener():

    """"The cache listener in order to make necessary operations with cache before it cleared automatically"""

    def __init__(self, redis, app: Quart):
        self.redis = redis
        self.app = app
        self.ActiveListener = True
        
        
    @global_error_handler_async
    async def on_stop_app(self):

        """It works when the app was stopped manually (like Ctrl+C in terminal)
        We should write the new datetime_shown to the database and after that clear cache"""
        
        keys = await self.redis.keys('*')    
        decoded_keys = [key.decode('utf-8') for key in keys]  
                            #originally keys are bytes like [b'key1', b'key2', b'key3']
        for k in decoded_keys:
            GottenData = await self.redis.get(k)
            if GottenData:
                CachedList = json.loads(GottenData)
                await send_cach_to_db(CachedList)
            await self.redis.delete(k)


    @global_error_handler_async
    async def cache_event_listener(self):

        """This function works in the background task and ensures that the 
        new datetime_shown is sent to the database before the cache is cleared"""

        i = 0
        while self.ActiveListener:
            #settings.CACHE_DEFAULT_TIMEOUT - the expiration time in sec
            #settings.CACHE_CHECK_TIMEOUT - the interval after which we check the cache
            if i >= settings.CACHE_DEFAULT_TIMEOUT/settings.CACHE_CHECK_TIMEOUT:
                i = 0
                
                keys = await self.redis.keys('*')
                decoded_keys = [key.decode('utf-8') for key in keys]
                for k in decoded_keys:
                    ttl = await self.redis.ttl(k)  #ttl seconds left before the key will be deleted
                    if ttl <= settings.CACHE_CHECK_TIMEOUT:  
                        GottenData = await self.redis.get(k)
                        
                        if GottenData:
                            CachedList = json.loads(GottenData)
                            await send_cach_to_db(CachedList)
                            await self.redis.delete(k)
            i += 1                 
            await asyncio.sleep(1)


    @global_error_handler_sync
    def start_cache_listener(self):

        """we start background task for cache processing"""

        self.ActiveListener = True
        self.app.add_background_task(self.cache_event_listener) 


    def stop_cache_listener(self):
        self.ActiveListener = False


@global_error_handler_async
async def send_cach_to_db(Tests_List):

    """the function for sending the new datetime_shown to the database"""

    async for session in get_async_session():
        for k in Tests_List:       
            onetest = CachedTests(**k)
            date_time_in_format = None
            if onetest.datetime_shown != None:
                date_time_in_format = datetime.fromisoformat(onetest.datetime_shown)
            statement = update(Questions).where(Questions.id == onetest.ID).values(datetime_shown = date_time_in_format)
            await session.execute(statement)
            await session.commit()


