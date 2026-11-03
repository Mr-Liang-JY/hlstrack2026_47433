"""Move cyclic-GC pauses outside finite video playback; preserve caller state."""
import gc,time
class PlaybackGuard:
    def __init__(self,suspend=True):self.suspend=suspend;self.active=False;self.measurement={}
    def start(self):
        self.previous=gc.isenabled();begin=time.perf_counter();collected=gc.collect()
        self.before=gc.get_stats()
        self.measurement=dict(startup_gc_s=time.perf_counter()-begin,startup_collected=collected,
                              automatic_gc_suspended=bool(self.suspend and self.previous))
        if self.suspend:gc.disable()
        self.active=True
    def close(self):
        if not self.active:return
        after=gc.get_stats()
        self.measurement['collections_during_playback']=[b['collections']-a['collections'] for a,b in zip(self.before,after)]
        if self.previous:gc.enable()
        else:gc.disable()
        self.measurement['caller_gc_state_restored']=gc.isenabled()==self.previous
        self.active=False
