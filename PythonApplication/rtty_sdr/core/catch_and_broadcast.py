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
            
            mangled_name = f"_{self.__class__.__name__}__registry"
            registry = getattr(self, mangled_name, None)
            
            if registry is not None:
                try:
                    temp_pubsub = PubSub([], registry)
                    temp_pubsub.publish_message("system.shutdown", None)
                    logger.debug("FullStopCommand broadcasted successfully via temporary PubSub.")
                    
                    time.sleep(0.1)
                except Exception as pubsub_error:
                    logger.error(f"Failed to broadcast shutdown: {pubsub_error}")
            else:
                logger.error(f"Could not broadcast shutdown: '{mangled_name}' not found on instance.")
            return 
            
    return wrapper
