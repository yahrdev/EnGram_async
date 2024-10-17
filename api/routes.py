from schemas import TestsToDB, GettedTests, Message, OptionsTest, ToValidateLevel
from models import Options, Questions, Levels, get_async_session
from sqlalchemy.orm import aliased
from sqlalchemy import select
import logging
from typing import List
from const import TxtData, BadRequestErrorInfo, NotFoundErrorInfo, InternalErrorInfo
import config
from quart import Blueprint, request, current_app
from quart_schema import validate_request, validate_response, validate_querystring
from handlers import global_error_handler_async, NoTestsError, WrongLevelError, log_raise_error
from datetime import datetime, timezone


#logger = getLogger(__name__)
""" basicConfig(filemode='a+', 
            format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s'
)  #Change the configuration to ensure understandable errors are displayed in the terminal """

eng_bp = Blueprint('eng_bp', __name__)



     

@eng_bp.route(TxtData.GetTestRoute, methods=["GET"])    #/testroutes/gettests
@validate_querystring(ToValidateLevel)
@validate_response(GettedTests, 200)
@validate_response(Message, NotFoundErrorInfo.ErrorCode)
@validate_response(Message, InternalErrorInfo.ErrorCode)
@validate_response(Message, BadRequestErrorInfo.ErrorCode)
async def GetTests(query_args: ToValidateLevel):
    """The route for a test retrieving.
    This route retrieves 1 test from the database or cache"""

    # Before a test is returned, the route retrieves it from the cache. 
    # If there are no tests in the cache, a new group of tests is taken 
    # from the database and written to the cache.
     
    data = request.args    #We do not use the standard method of data validation because we want to generate our own error.
    try:
        level = data.get(TxtData.Level_name)
        if not level in Levels._value2member_map_:     #a list of available levels in the enum
            raise WrongLevelError()
        EngCache = current_app.config['EngCache']  #get cache from the app.py
        OneTest = await EngCache.get_cached_test(level)  #try to take a test from the cache
        if not OneTest:
            TestsList = await _get_tests(level)   #try to take from the db
            await EngCache.addtocache(TestsList, level)
            OneTest = await EngCache.get_cached_test(level)
            if not OneTest:
                raise NoTestsError()
        return OneTest
    
    except Exception as e:
        log_raise_error(e, GetTests)
        raise e

    




@eng_bp.route(TxtData.UpdateTestRoute, methods=["POST"]) #/testroutes/updatestatus
@validate_request(TestsToDB)
@validate_response(Message, 200)
@validate_response(Message, InternalErrorInfo.ErrorCode)
@validate_response(Message, BadRequestErrorInfo.ErrorCode)
async def UpdateStatus(data: TestsToDB):
    """The route for updating data in the cache/db.
    This route updates the datetime_shown value for the tests that were shown. 
    If the ID is an integer but does not exist, a 200 status will still be returned."""

    # We update the 'Shown' and 'datetime_shown' values, so the tests will not be repeated
    try:
        onetest = data
        EngCache = current_app.config['EngCache']
        if not onetest.datetime_shown:
            onetest.datetime_shown = datetime.now(timezone.utc).isoformat()
        result = await EngCache.update_cached_tests(onetest.Level.value, onetest.ID, onetest.datetime_shown)
        if not result:
            logging.warning(TxtData.NonSuccessfulUpdate.format(onetest.ID, onetest.Level.value))

        return Message(message=TxtData.SuccessfulUpdate).model_dump(), 200
        #we return Success for both cases: a test is in the cache or not. For the second case we show the warning in the terminal
    except Exception as e:
        log_raise_error(e, UpdateStatus)
        raise e


@global_error_handler_async
async def _get_tests(Level) -> List[dict]:

    """The function for tests retrieving from the db"""

    async for session in get_async_session():
        SubqStmt = select(Questions).where(Questions.level == Level).order_by(Questions.datetime_shown).limit(config.settings.NUMBER_OF_TESTS) 
        #select * from question order by datetime_shown limit config.settings.NUMBER_OF_TESTS

        Subquery = SubqStmt.subquery()
        QuestionsAlias = aliased(Questions, Subquery) 
        #apply Questions class to Subquery in order to create necessary structure

        ResultStmt = select(QuestionsAlias, Options).join_from(QuestionsAlias, Options, QuestionsAlias.id == Options.question_id, isouter=False)
        #select Q.*, options.* from (Subquery) as Q inner join Options on Q.id = options.question_id;
        
        Result = await session.execute(ResultStmt)
    if not Result:
        TestsList = [] 
        raise NoTestsError()


    QuestionsList = []   #Received questions models list
    OptionsList = []    #Received options models list
    TestsList = []   #json to return
    idis = set()     #Received questions' IDs


    """ Result.fetchall() returns a list of tuples filled out by SQLAlchemy models
    We try to separate Questions from Options below 
    Our goal - to have the following json:
        {
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
            "datetime_shown": datetime
        }   
    """

    for q, o in Result.fetchall():  #separation
        q: Questions
        o: Options
        
        OptionsList.append(o)

        if not q.id in idis:   #select only unique models without duplicates
            QuestionsList.append(q)   
        idis.add(q.id)
    

    for q in QuestionsList:   #joining together to the json
        q: Questions
        OptionsShortList = []  #short options list without question_id
        for o in OptionsList:
            o: Options
            
            if q.id == o.question_id:
                OptionsModel = OptionsTest(option_id=o.option_id, option_text=o.option_text)
                OptionsShortList.append(OptionsModel.model_dump())


        newtest = GettedTests(ID=q.id,
                            Question=q.question,
                            Options=OptionsShortList,
                            correct_option_id=q.correct_id,
                            explanation= q.explanation,
                            datetime_shown=q.datetime_shown                                        
                            ) 

        TestsList.append(newtest.model_dump())
    return TestsList



