import importlib.util, pathlib, time, random, os
os.environ['OMP_NUM_THREADS'] = '1'

spec = importlib.util.spec_from_file_location(
    'clustering_service',
    pathlib.Path('travel_logic/services/clustering_service.py')
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
CS = mod.ClusteringService

random.seed(99)
JEJU = [{'id':i,'name':f'장소{i}','lat':33.0+random.uniform(0,1.2),'lng':126.0+random.uniform(0,1.4)} for i in range(1,21)]

# warm-up
CS.cluster_by_day(JEJU, 4)

times = []
for _ in range(3):
    t0 = time.perf_counter()
    CS.cluster_by_day(JEJU, 4)
    times.append((time.perf_counter()-t0)*1000)

avg = sum(times)/len(times)
print(f'warm-up 후 평균 처리시간: {avg:.1f}ms')
print(f'처리시간 < 200ms: {avg < 200}')

BIG = [{'id':i,'name':f'장소{i}','lat':33.0+random.uniform(0,2.0),'lng':126.0+random.uniform(0,2.0)} for i in range(100)]
t0 = time.perf_counter()
c_big, _ = CS.cluster_by_day(BIG, 7)
big_ms = (time.perf_counter()-t0)*1000
s_big = [len(c) for c in c_big]
print(f'100개/7일: {big_ms:.1f}ms, sizes={sorted(s_big)}, diff={max(s_big)-min(s_big)}')
