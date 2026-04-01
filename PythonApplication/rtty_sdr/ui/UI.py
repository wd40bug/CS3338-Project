from rtty_sdr.core.module import Module
import time

class MockUI(Module):
    def run(self) -> None:
        print("[UI] Started in Main Thread. Press Ctrl+C to exit.")
        try:
            # GUI main loops (like PyQt's app.exec_()) block here
            while True:
                time.sleep(0.1) 
        except KeyboardInterrupt:
            print("\n[UI] Shutting down...")
