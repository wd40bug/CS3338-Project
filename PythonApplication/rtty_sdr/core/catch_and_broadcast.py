import sys
import time
import functools
from loguru import logger

from rtty_sdr.comms.pubsub import PubSub

def catch_and_broadcast(func):
    """
    Wraps a background thread method. 
    Dynamically extracts the registry, spins up a temporary PubSub,
    broadcasts the shutdown, and kills the thread.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
            
        except Exception as e:
            logger.exception(f"Fatal crash in {self.__class__.__name__}: {e}")
            
            # 1. Dynamically find the private __registry variable using name mangling
            mangled_name = f"_{self.__class__.__name__}__registry"
            registry = getattr(self, mangled_name, None)
            
            if registry is not None:
                try:
                    # 2. Spin up a temporary, throw-away PubSub instance
                    # We pass an empty list because we don't need to subscribe to anything
                    temp_pubsub = PubSub([], registry)
                    temp_pubsub.publish_message("system.shutdown", None)
                    logger.debug("Poison pill broadcasted successfully via temporary PubSub.")
                    
                    # 3. Give the ZMQ C++ background thread 100ms to put the message on the wire
                    time.sleep(0.1)
                except Exception as pubsub_error:
                    logger.error(f"Failed to broadcast shutdown: {pubsub_error}")
            else:
                logger.error(f"Could not broadcast shutdown: '{mangled_name}' not found on instance.")
            return 
            
    return wrapper
