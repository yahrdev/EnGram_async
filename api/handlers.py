import logging
from const import TxtData, NotFoundErrorInfo, InternalErrorInfo, BadRequestErrorInfo, NotFoundErrorInfo
from werkzeug.exceptions import HTTPException
import functools
from schemas import Message, Levels

def global_error_handler_async(func):

    """general handler for Internal Server Error logging of async functions"""

    @functools.wraps(func) #in order to see original function name as otherwise the problem appears in UpdateStatus route
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            log_raise_error(e, func)
    return wrapper


def global_error_handler_sync(func):

    """general handler for Internal Server Error logging of sync functions"""

    @functools.wraps(func) 
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log_raise_error(e, func)
    return wrapper



def log_raise_error(exception, func):

    """The function for errors detailed handling"""
    if not hasattr(exception, '_logged'): #check whether was logged already
        module_name = func.__module__
        function_name = func.__name__ 
        error_text = TxtData.ErrorArose.format(function_name, module_name, str(exception))
        try:
            logging.error(error_text)

        except Exception as e:  #if smth happend with the logger
            print(TxtData.LoggerError.format(error_text, str(e)))

        setattr(exception, '_logged', True)  
            #add a new attribute in order to mark the error as logged already. 
            #Otherwise we will see the same error for each function in the stack
        raise



class NoTestsError(HTTPException):

    """404 error for the case when there are no tests in db"""

    code = NotFoundErrorInfo.ErrorCode
    description = NotFoundErrorInfo.NoTestsText 


class WrongLevelError(HTTPException):

    """400 error for the case when wrong level"""

    code = BadRequestErrorInfo.ErrorCode
    description = BadRequestErrorInfo.ErrorText


    


async def handle_request_validation_error(error):

    """400. We detail the error that arises when a user sends incorrect data in JSON"""

    try:
        return Message(message=[{"field": err["loc"][0], "details": err["msg"]} for err in error.validation_error.errors()]), BadRequestErrorInfo.ErrorCode
    except:
        return Message(message=str(error)), BadRequestErrorInfo.ErrorCode


async def handle_bad_request_error(error):

    """400. We detail the error that arises when a user sends incorrect data (not json for example)"""

    return Message(message=str(error)), BadRequestErrorInfo.ErrorCode


async def handle_wrong_level_error(error):

    """400. We detail the error that arises when a user sends wrong level"""

    return Message(message=TxtData.WrongLevelError.format(list(Levels._value2member_map_))), BadRequestErrorInfo.ErrorCode


async def handle_not_found_error(error):

    """404. We detail any 404 error"""

    return Message(message=str(error)), NotFoundErrorInfo.ErrorCode


async def handle_no_tests_error(error):

    """404. We detail the error that arises when there are not tests in db"""

    return Message(message=NotFoundErrorInfo.NoTestsText), NotFoundErrorInfo.ErrorCode



async def handle_internal_error(error):

    """500. We change the format of 500 error"""

    return Message(message=InternalErrorInfo.ErrorText), InternalErrorInfo.ErrorCode