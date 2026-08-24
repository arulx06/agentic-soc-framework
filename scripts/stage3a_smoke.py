"""Quick Stage-3A smoke: health, sessions, replay lifecycle, SREP, snapshots."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from backend.app.main import app

c = TestClient(app)
h = c.get('/api/v1/health').json()
print('health ok:', h['service'], '| scientific_ready:', h['scientific_ready'])
s = c.get('/api/v1/sessions').json()
print('sessions:', len(s['sessions']), '| default:', s['default_session'][:40])
rid = c.post('/api/v1/replays', json={'session_id': s['default_session'], 'source_mode': 'feature_store', 'pacing': 'max'}).json()['replay_id']
c.post(f'/api/v1/replays/{rid}/play')
deadline = time.time() + 90
st = None
while time.time() < deadline:
    st = c.get(f'/api/v1/replays/{rid}').json()
    if st['state'] == 'COMPLETED':
        break
    time.sleep(0.3)
print('final state:', st['state'], '| findings:', st['findings_emitted'], '| seq:', st['sequence_number'])
sr = c.get(f'/api/v1/replays/{rid}/srep').json()
print('srep mode:', sr['mode'], '| blast:', sr.get('defended_blast_radius'))
ds = c.get(f'/api/v1/replays/{rid}/device-state').json()
soil = next(d for d in ds['devices'] if d['entity_id'] == 'soil-sensor')
print('soil device-state:', {k: soil[k] for k in ('behavior_supported', 'behavior_risk', 'network_observed')})
gr = c.get(f'/api/v1/replays/{rid}/graphs/device-risk').json()
cg = c.get(f'/api/v1/replays/{rid}/graphs/communication').json()
print('risk graph nodes/edges:', len(gr['nodes']), len(gr['edges']), '| comm edges:', len(cg['edges']))
snap = c.post('/api/v1/snapshots').json()
lst = c.get('/api/v1/snapshots').json()['snapshots']
rd = c.get(f"/api/v1/snapshots/{lst[-1]['snapshot_id']}").json()
print('snapshot roundtrip:', rd['schema_version'] == 'saved_replay_snapshot_v1', '| devices:', len(rd['device_states']))
