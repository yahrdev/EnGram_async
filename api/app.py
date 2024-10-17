"""The main file"""

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#without this part, we lose the ability to run the app either from the terminal or from the file.

from config import settings
from routes import eng_bp
from cache_utils import EngCache, CacheListener, initcache
from quart import Quart, redirect
from quart_schema import QuartSchema
import asyncio
from quart_schema import RequestSchemaValidationError
from handlers import (
    handle_request_validation_error,
    handle_bad_request_error,
    handle_not_found_error,
    handle_no_tests_error,
    handle_internal_error,
    NoTestsError,
    WrongLevelError,
    handle_wrong_level_error,  
    global_error_handler_sync
)

@global_error_handler_sync
def create_app():
    app = Quart(__name__)
    QuartSchema(app) #initialise Quart-Schema documentation
    
    @app.route('/', methods=["GET"])   #for redirecting from http://127.0.0.1:8000/
    async def index():

        """redirect to /docs"""

        return redirect('/docs')
    
    #handlers registering
    app.errorhandler(RequestSchemaValidationError)(handle_request_validation_error)
    app.errorhandler(400)(handle_bad_request_error)
    app.errorhandler(404)(handle_not_found_error)
    app.errorhandler(NoTestsError)(handle_no_tests_error)
    app.errorhandler(500)(handle_internal_error)
    app.errorhandler(WrongLevelError)(handle_wrong_level_error)


    app.register_blueprint(eng_bp, url_prefix='')  #add routes
    
    return app


@global_error_handler_sync
def setup_cache(app: Quart):
    """Initialize the cache classes for saving and reading to/from the cache and for cache listening"""

    redis = initcache()
    engcache = EngCache(redis)  #init the class for cache processing
    cache_listener = CacheListener(redis, app)   #init a class to listen the cache
    app.config['EngCache'] = engcache #config in order to pass EngCache class from cache_utils.py to routes.py
    return cache_listener


def run_app():
    app = create_app()
    cache_listener = setup_cache(app)
    
    @app.before_serving
    async def before_serving():
        """implement the background task"""
        cache_listener.start_cache_listener() 

    @app.after_serving
    async def after_serving():
        """when clicking Ctrl+C in the terminal"""
        await cache_listener.on_stop_app()
        cache_listener.stop_cache_listener()
    return app

    


if __name__ == '__main__':
    
    app = run_app()

    loop = asyncio.get_event_loop()   
        #obtain a loop in order to use it for the app and for the cache_listener

    loop.run_until_complete(app.run_task(host= settings.SERVER_HOST, port= settings.SERVER_PORT))
        # We start our app and the loop will keep running until the task (the app) completes.
        # The event loop won't be closed until the application has fully finished its execution.

        

