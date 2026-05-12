"use client";

import { useState, useEffect, useRef } from "react";
import { Map, Calendar, Users, ArrowLeft, ExternalLink, RefreshCw, Star, MapPin, Clock, Plane, Hotel, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import Link from "next/link";

const API_BASE = "https://pick-and-go-1.onrender.com/api/v1";

// ── Google Maps 렌더러 (iframe 방식) ──────────────────────────
function MapPanel({ markers, path, googleKey }: {
  markers: { lat: number; lng: number; title: string }[];
  path: { lat: number; lng: number }[];
  googleKey: string;
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const mapHtml = `<!DOCTYPE html><html><head>
  <style>
    html,body{margin:0;height:100%;font-family:sans-serif;}
    #map{height:100%;}
    .info-window{padding:6px 10px;font-size:13px;font-weight:700;color:#1e3a8a;white-space:nowrap;}
  </style>
  </head><body>
  <div id="map"></div>
  <script>
  function init(){
    const markers=${JSON.stringify(markers)};
    const path=${JSON.stringify(path)};
    if(!markers.length){document.body.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94a3b8;font-size:14px;">표시할 장소가 없습니다.</div>';return;}
    const avg={lat:markers.reduce((s,m)=>s+m.lat,0)/markers.length,lng:markers.reduce((s,m)=>s+m.lng,0)/markers.length};
    const map=new google.maps.Map(document.getElementById('map'),{zoom:12,center:avg,mapTypeControl:false,streetViewControl:false,fullscreenControl:false});
    if(path.length>1) new google.maps.Polyline({path,map,strokeColor:'#3B82F6',strokeWeight:4,strokeOpacity:0.8});
    const bounds=new google.maps.LatLngBounds();
    markers.forEach((m,i)=>{
      const pos={lat:m.lat,lng:m.lng};
      const marker=new google.maps.Marker({position:pos,map,label:{text:(i+1).toString(),color:'#fff',fontWeight:'bold',fontSize:'12px'},title:m.title});
      const iw=new google.maps.InfoWindow({content:'<div class="info-window">'+m.title+'</div>'});
      marker.addListener('click',()=>iw.open(map,marker));
      bounds.extend(pos);
    });
    if(markers.length>1) map.fitBounds(bounds);
  }
  </script>
  <script src="https://maps.googleapis.com/maps/api/js?key=${googleKey}&callback=init" async defer></script>
  </body></html>`;

  if (!googleKey) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-slate-50 rounded-3xl border-2 border-dashed border-slate-200 text-slate-400">
        <Map className="w-14 h-14 mb-3 text-blue-200" />
        <p className="font-bold text-slate-500">지도를 불러올 수 없습니다</p>
        <p className="text-sm mt-1">Google Maps API Key가 필요합니다.</p>
      </div>
    );
  }

  return (
    <iframe
      ref={iframeRef}
      srcDoc={mapHtml}
      className="w-full h-full rounded-3xl border border-slate-200 shadow-lg"
      sandbox="allow-scripts allow-same-origin"
    />
  );
}

// ── 장소 카드 ────────────────────────────────────────────────
function PlaceCard({ place, index, destCity }: { place: any; index: number; destCity: string }) {
  const url = place.url || `https://www.google.com/search?q=${encodeURIComponent(place.name + " " + destCity)}`;
  return (
    <div className="group flex gap-4 p-4 bg-white/90 backdrop-blur-sm border border-slate-100 rounded-2xl hover:bg-white transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-blue-900/5">
      {/* 인덱스 번호 */}
      <div className="shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-black text-sm shadow-md shadow-blue-500/30">
        {index + 1}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1.5">
          <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded-md text-xs font-bold font-mono border border-blue-100">
            {place.time}
          </span>
          <span className="px-2 py-0.5 bg-slate-50 border border-slate-200 text-slate-500 rounded-md text-xs font-medium">
            {place.type}
          </span>
        </div>
        <h5 className="text-base font-bold text-slate-800 mb-1 group-hover:text-blue-600 transition-colors truncate">
          {place.name}
        </h5>
        <p className="text-sm text-slate-500 leading-relaxed mb-3 line-clamp-2">{place.desc}</p>
        {place.img && (
          <img
            src={place.img}
            alt={place.name}
            className="w-full h-28 object-cover rounded-xl mb-3 border border-slate-100"
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        )}
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 hover:text-emerald-500 transition-colors bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-100 hover:bg-emerald-100"
        >
          상세 보기 <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}

// ── 메인 컴포넌트 ────────────────────────────────────────────
export default function ResultPage() {
  const [activeTab, setActiveTab]         = useState(0);
  const [selectedDay, setSelectedDay]     = useState<"all" | number>("all");
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [apiData, setApiData]             = useState<any>(null);
  const [userData, setUserData]           = useState<any>(null);
  const [isLoading, setIsLoading]         = useState(true);
  const [expandedDays, setExpandedDays]   = useState<number[]>([]);
  const GOOGLE_KEY                        = process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY || "";

  useEffect(() => {
    const savedResult = localStorage.getItem("api_result");
    const savedForm   = localStorage.getItem("form_data");
    if (savedResult && savedForm) {
      try {
        setApiData(JSON.parse(savedResult));
        setUserData(JSON.parse(savedForm));
      } catch {}
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    if (apiData?.plans) {
      const firstPlan = apiData.plans[0];
      setExpandedDays(firstPlan?.days?.map((d: any) => d.day) ?? []);
    }
  }, [apiData, activeTab]);

  const handleRegenerate = async () => {
    if (!userData) return;
    setIsRegenerating(true);
    try {
      const res = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(userData),
      });
      if (res.ok) {
        const newData = await res.json();
        setApiData(newData);
        localStorage.setItem("api_result", JSON.stringify(newData));
        setActiveTab(0);
        setSelectedDay("all");
      } else {
        alert("일정 다시 생성 실패!");
      }
    } catch { alert("서버 오류가 발생했습니다."); }
    finally { setIsRegenerating(false); }
  };

  const toggleDay = (day: number) =>
    setExpandedDays(prev => prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]);

  // ── 로딩 / 빈 데이터 처리 ──
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-sky-100 flex flex-col items-center justify-center text-slate-600">
        <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-4" />
        <p className="font-bold text-lg">일정을 불러오고 있습니다...</p>
      </div>
    );
  }

  if (!apiData?.plans?.length) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-sky-100 flex flex-col items-center justify-center text-center p-6">
        <MapPin className="w-16 h-16 text-blue-200 mb-4" />
        <h2 className="text-2xl font-black text-slate-700 mb-2">생성된 일정 데이터가 없습니다.</h2>
        <p className="text-slate-500 mb-8">메인 페이지에서 여행 조건을 입력하고 일정을 생성해주세요.</p>
        <Link href="/" className="px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-2xl transition-colors shadow-lg shadow-blue-500/30">
          ← 입력 화면으로
        </Link>
      </div>
    );
  }

  const activePlan = apiData.plans[activeTab] ?? apiData.plans[0];
  const destCity   = userData?.dest_city ?? "목적지";
  const startDate  = userData?.start_date ?? "";
  const endDate    = userData?.end_date ?? "";
  const people     = userData?.people ?? 1;
  const styles     = (userData?.style ?? []).join(" · ");
  const isDomestic = ["서울","제주","부산","강원","강릉","속초","여수","경주","전주","인천","대구","광주","수원","울산"].some(c => destCity.includes(c));

  // 지도 마커 계산
  const getMarkers = () => {
    const days = selectedDay === "all"
      ? activePlan.days
      : activePlan.days.filter((d: any) => d.day === selectedDay);
    const markers: { lat: number; lng: number; title: string }[] = [];
    const path:    { lat: number; lng: number }[] = [];
    for (const d of days) {
      for (const p of d.places) {
        try {
          const lat = parseFloat(p.lat), lng = parseFloat(p.lng);
          if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
            markers.push({ lat, lng, title: p.name });
            path.push({ lat, lng });
          }
        } catch {}
      }
    }
    return { markers, path };
  };
  const { markers, path } = getMarkers();

  return (
    <div className="min-h-screen bg-sky-50 text-slate-800 font-sans">
      <div className="fixed inset-0 -z-10 bg-gradient-to-br from-blue-50 via-white to-sky-100" />

      {/* ── Sticky Nav ── */}
      <nav className="border-b border-sky-100 bg-white/80 backdrop-blur-md sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-500 hover:text-slate-800">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <span className="text-lg font-black bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-sky-500">
              Pick &amp; Go
            </span>
          </div>
          <button
            onClick={handleRegenerate}
            disabled={isRegenerating}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm font-bold rounded-xl transition-colors shadow-lg shadow-blue-500/20"
          >
            <RefreshCw className={`w-4 h-4 ${isRegenerating ? "animate-spin" : ""}`} />
            {isRegenerating ? "생성 중..." : "다시 추천받기"}
          </button>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">

        {/* ── 헤더 ── */}
        <div className="mb-8">
          <div className="flex flex-wrap gap-2 mb-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-sm font-bold">
              {isDomestic ? "🇰🇷 국내여행" : "🌏 해외여행"}
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-50 border border-slate-200 text-slate-600 text-sm font-semibold">
              <Calendar className="w-3.5 h-3.5" /> {startDate} ~ {endDate}
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm font-semibold">
              <Users className="w-3.5 h-3.5" /> {people}명
            </span>
            {styles && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-50 border border-purple-200 text-purple-700 text-sm font-semibold">
                <Sparkles className="w-3.5 h-3.5" /> {styles}
              </span>
            )}
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-slate-800">
            {destCity} 추천 여행 코스
          </h1>
        </div>

        {/* ── 탭 ── */}
        <div className="flex space-x-2 p-1.5 bg-white/60 backdrop-blur-xl border border-slate-200 rounded-2xl mb-8 overflow-x-auto shadow-sm">
          {apiData.plans.map((plan: any, idx: number) => (
            <button
              key={idx}
              onClick={() => { setActiveTab(idx); setSelectedDay("all"); }}
              className={`flex-none px-5 py-2.5 rounded-xl font-bold text-sm transition-all duration-300 whitespace-nowrap ${
                activeTab === idx
                  ? "bg-white text-blue-700 shadow-md border border-slate-100 -translate-y-0.5"
                  : "text-slate-500 hover:text-slate-800 hover:bg-white/60"
              }`}
            >
              {idx === 0 ? "⭐" : "📋"} 안 {idx + 1}: {plan.theme}
            </button>
          ))}
        </div>

        {/* ── 적합도 바 ── */}
        <div className="flex items-center gap-4 mb-8 p-5 bg-white/80 border border-slate-100 rounded-2xl shadow-sm">
          <div className="flex items-center gap-3 shrink-0">
            <Star className="w-5 h-5 text-amber-400 fill-amber-400" />
            <span className="font-black text-2xl text-blue-700">{activePlan.score}%</span>
            <span className="text-sm text-slate-500 font-semibold">적합도</span>
          </div>
          <div className="flex-1 h-2.5 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-700"
              style={{ width: `${activePlan.score}%` }}
            />
          </div>
          <p className="text-slate-600 font-medium text-sm hidden md:block max-w-sm">{activePlan.desc}</p>
        </div>

        {/* ── 메인 그리드 ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

          {/* 일정 타임라인 */}
          <div className="lg:col-span-5 space-y-4">
            <h2 className="text-xl font-bold flex items-center gap-2 text-slate-800">
              <Calendar className="w-5 h-5 text-blue-500" /> 상세 일정
            </h2>

            {activePlan.days.map((dayObj: any) => {
              const isExpanded = expandedDays.includes(dayObj.day);
              return (
                <div key={dayObj.day} className="bg-white/90 border border-slate-100 rounded-2xl overflow-hidden shadow-sm">
                  <button
                    onClick={() => toggleDay(dayObj.day)}
                    className="w-full flex items-center justify-between px-5 py-4 hover:bg-blue-50/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-black text-sm">
                        {dayObj.day}
                      </div>
                      <span className="font-bold text-slate-800">Day {dayObj.day}</span>
                      <span className="text-xs text-slate-400 font-medium">{dayObj.places.length}개 장소</span>
                    </div>
                    {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                  </button>
                  {isExpanded && (
                    <div className="px-4 pb-4 space-y-3 border-t border-slate-50">
                      {dayObj.places.map((place: any, pIdx: number) => (
                        <PlaceCard key={pIdx} place={place} index={pIdx} destCity={destCity} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* 예약 버튼 */}
            <button className="w-full flex items-center justify-center gap-3 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-2xl shadow-xl shadow-blue-500/30 transition-all duration-300 hover:-translate-y-0.5 group">
              <Plane className="w-5 h-5 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
              이 코스로 항공 + 숙소 예약하기
              <Hotel className="w-5 h-5" />
            </button>
          </div>

          {/* 지도 */}
          <div className="lg:col-span-7">
            <div className="sticky top-24">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold flex items-center gap-2 text-slate-800">
                  <Map className="w-5 h-5 text-purple-500" /> 이동 동선
                </h2>
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-slate-400" />
                  <select
                    value={selectedDay === "all" ? "all" : selectedDay}
                    onChange={(e) => setSelectedDay(e.target.value === "all" ? "all" : parseInt(e.target.value))}
                    className="bg-white border border-slate-200 text-slate-700 font-semibold text-sm rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
                  >
                    <option value="all">전체 동선</option>
                    {activePlan.days.map((d: any) => (
                      <option key={d.day} value={d.day}>Day {d.day}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="w-full h-[600px]">
                <MapPanel markers={markers} path={path} googleKey={GOOGLE_KEY} />
              </div>
              <p className="text-center text-xs text-slate-400 mt-2 font-medium">
                마커를 클릭하면 장소 이름을 확인할 수 있습니다.
              </p>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
