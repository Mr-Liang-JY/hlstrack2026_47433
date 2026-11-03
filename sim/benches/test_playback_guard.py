from pathlib import Path
import gc,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from playback_guard import PlaybackGuard
class GuardChecks(unittest.TestCase):
    def test_restores_after_player_error(self):
        original=gc.isenabled();guard=PlaybackGuard()
        try:
            gc.enable();guard.start();self.assertFalse(gc.isenabled())
            try:raise RuntimeError('simulated player failure')
            except RuntimeError:pass
            finally:guard.close()
            self.assertTrue(gc.isenabled());self.assertTrue(guard.measurement['caller_gc_state_restored'])
        finally:
            if original:gc.enable()
            else:gc.disable()
    def test_preserves_disabled_caller(self):
        original=gc.isenabled();guard=PlaybackGuard()
        try:
            gc.disable();guard.start();guard.close();self.assertFalse(gc.isenabled())
        finally:
            if original:gc.enable()
            else:gc.disable()
    def test_unbounded_mode_keeps_automatic_gc(self):
        original=gc.isenabled();guard=PlaybackGuard(suspend=False)
        try:
            gc.enable();guard.start();self.assertTrue(gc.isenabled());guard.close()
        finally:
            if original:gc.enable()
            else:gc.disable()
if __name__=='__main__':unittest.main(verbosity=2)
