"use client";

import { useState, useEffect } from "react";
import { Map, Calendar, Navigation, ArrowLeft, ExternalLink, RefreshCw, Database } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function ResultPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState(0);
  const [selectedDay, setSelectedDay] = useState("all");
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [apiData, setApiData] = useState<any>(null);
  const [userData, setUserData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Load from localStorage on mount
    const savedResult = localStorage.getItem("api_result");
    const savedForm = localStorage.getItem("form_data");
    
    if (savedResult && savedForm) {
      try {
        setApiData(JSON.parse(savedResult));
        setUserData(JSON.parse(savedForm));
      } catch (e) {
        console.error("Failed to parse saved data", e);
      }
    }
    setIsLoading(false);
  }, []);

  const handleRegenerate = async () => {
    if (!userData) return;
    setIsRegenerating(true);
    try {
      const res = await fetch("https://pick-and-go-1.onrender.com/api/v1/generate", {
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
    } catch (e) {
      console.error(e);
      alert("서버 오류가 발생했습니다.");
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleUpdateDB = async () => {
    if (!userData) return;
    if (!confirm("백그라운드에서 장소 데이터를 새로 수집합니다. 진행하시겠습니까?")) return;
    
    try {
      const res = await fetch("https://pick-and-go-1.onrender.com/api/v1/update-db", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dest_city: userData.dest_city, styles: userData.style }),
      });
      if (res.ok) {
        alert("DB 업데이트 요청이 성공적으로 접수되었습니다! 잠시 후 다시 추천받기를 눌러주세요.");
      }
    } catch (e) {
      alert("DB 업데이트 요청 실패");
    }
  };

  if (isLoading) {
    return <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-white"><RefreshCw className="w-8 h-8 animate-spin mb-4 text-indigo-500" />데이터 불러오는 중...</div>;
  }

  if (!apiData || !apiData.plans || apiData.plans.length === 0) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-white p-4 text-center">
        <h2 className="text-2xl font-bold mb-4 text-red-400">생성된 일정 데이터가 없습니다.</h2>
        <p className="text-slate-400 mb-8">메인 페이지에서 여행 조건을 다시 입력하고 일정을 생성해주세요.</p>
        <Link href="/" className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 rounded-xl transition-colors font-medium">돌아가기</Link>
      </div>
    );
  }

  const activePlan = apiData.plans[activeTab] || apiData.plans[0];
  const destCity = userData?.dest_city || "목적지";
  const people = userData?.people || 1;
  const isDomestic = ["서울", "제주", "부산", "강원", "강릉", "속초", "여수", "경주", "전주"].some(c => destCity.includes(c)) || userData?.is_korea;


  return (
    <div className="min-h-screen bg-sky-50 text-slate-800 font-sans selection:bg-blue-200">
      {/* 화사한 배경 그라데이션 */}
      <div className="fixed inset-0 -z-10 bg-gradient-to-br from-blue-50 via-white to-sky-100"></div>

      {/* Header Navigation */}
      <nav className="border-b border-sky-100 bg-white/70 backdrop-blur-md sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-500 hover:text-slate-800">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-sky-500">
              Pick & Go AI 여정
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-slate-50 text-slate-700 text-sm font-medium rounded-xl transition-colors border border-slate-200 shadow-sm">
              <Database className="w-4 h-4 text-emerald-500" /> DB 업데이트
            </button>
            <button 
              onClick={handleRegenerate}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-xl transition-colors shadow-lg shadow-blue-500/20">
              <RefreshCw className={`w-4 h-4 ${isRegenerating ? 'animate-spin' : ''}`} /> 
              {isRegenerating ? '생성 중...' : '다시 추천받기'}
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        
        {/* Title Area */}
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-sm font-bold mb-4">
            {isDomestic ? '🇰🇷 국내여행' : '🌍 해외여행'}
          </div>
          <h2 className="text-3xl md:text-4xl font-extrabold mb-2 text-slate-800">{destCity} 추천 여행 코스</h2>
          <p className="text-slate-600 font-medium">{people}명 · 선호 스타일: {userData?.style?.join(", ")}</p>
        </div>

        {/* Tabs */}
        <div className="flex space-x-2 p-1 bg-white/50 backdrop-blur-xl border border-slate-200 rounded-2xl mb-8 overflow-x-auto snap-x no-scrollbar shadow-sm">
          {apiData.plans.map((plan: any, idx: number) => (
            <button
              key={idx}
              onClick={() => { setActiveTab(idx); setSelectedDay("all"); }}
              className={`flex-none px-6 py-3 rounded-xl font-bold text-sm transition-all duration-300 ${
                activeTab === idx 
                  ? 'bg-white text-blue-700 shadow-md border border-slate-100 translate-y-[-2px]' 
                  : 'text-slate-500 hover:text-slate-800 hover:bg-white/60'
              }`}
            >
              {`안 ${idx + 1}: ${plan.theme}`}
            </button>
          ))}
        </div>

        {/* Plan Header Info */}
        <div className="flex flex-col md:flex-row items-center gap-4 p-5 mb-8 bg-blue-50 border border-blue-100 rounded-2xl shadow-sm">
          <div className="shrink-0 flex items-center justify-center w-16 h-16 rounded-full bg-white border border-blue-200 shadow-sm">
            <div className="text-center">
              <div className="text-xs font-bold text-blue-500">적합도</div>
              <div className="text-xl font-black text-blue-700">{activePlan.score}%</div>
            </div>
          </div>
          <p className="text-slate-700 text-lg leading-relaxed font-medium">{activePlan.desc}</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Timeline List (Left Side) */}
          <div className="lg:col-span-5 space-y-6">
            <h3 className="text-xl font-bold flex items-center gap-2 mb-4 text-slate-800">
              <Calendar className="w-5 h-5 text-blue-500" /> 상세 일정
            </h3>
            
            {activePlan.days.map((dayObj: any) => (
              <div key={dayObj.day} className="relative pl-6 pb-6 border-l-2 border-slate-200 last:border-l-transparent last:pb-0">
                <div className="absolute -left-[11px] top-0 w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center ring-4 ring-sky-50">
                  <div className="w-2 h-2 bg-white rounded-full"></div>
                </div>
                
                <h4 className="text-lg font-bold text-blue-600 mb-4 -mt-1 ml-2">Day {dayObj.day}</h4>
                
                <div className="space-y-4 ml-2">
                  {dayObj.places.map((place: any, pIdx: number) => (
                    <div key={pIdx} className="group p-5 bg-white/90 backdrop-blur-sm border border-slate-100 rounded-2xl hover:bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-blue-900/5">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="px-2.5 py-1 bg-blue-50 text-blue-600 rounded-md text-xs font-bold font-mono border border-blue-100">
                          {place.time}
                        </span>
                        <span className="px-2.5 py-1 bg-slate-50 border border-slate-200 text-slate-600 rounded-md text-xs font-medium">
                          {place.type}
                        </span>
                      </div>
                      <h5 className="text-lg font-bold text-slate-800 mb-1 group-hover:text-blue-600 transition-colors">{place.name}</h5>
                      <p className="text-sm text-slate-500 mb-4 leading-relaxed">{place.desc}</p>
                      
                      <a href={place.url || `https://www.google.com/search?q=${place.name}+${destCity}`} target="_blank" rel="noreferrer" 
                        className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-500 hover:text-emerald-400 transition-colors bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-100">
                        상세 및 예약 <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Map Area (Right Side) */}
          <div className="lg:col-span-7">
            <div className="sticky top-24">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold flex items-center gap-2 text-slate-800">
                  <Map className="w-5 h-5 text-purple-500" /> 이동 동선
                </h3>
                <select 
                  className="bg-white border border-slate-200 text-slate-700 font-medium text-sm rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
                  value={selectedDay}
                  onChange={(e) => setSelectedDay(e.target.value)}
                >
                  <option value="all">전체 동선</option>
                  {activePlan.days.map((d: any) => (
                    <option key={d.day} value={d.day}>Day {d.day}</option>
                  ))}
                </select>
              </div>
              
              <div className="w-full h-[600px] bg-white rounded-3xl border border-slate-200 overflow-hidden flex flex-col items-center justify-center relative shadow-xl shadow-slate-200/50">
                <Navigation className="w-16 h-16 text-blue-200 mb-4" />
                <p className="text-slate-600 font-bold z-10 text-lg">지도가 표시될 영역입니다</p>
                <p className="text-sm text-slate-400 z-10 mt-2 font-medium">Google Maps / Kakao Maps 연동 대기중</p>
                
                {/* Visual Placeholder Pattern - Bright */}
                <div className="absolute inset-0 opacity-[0.03]" style={{ backgroundImage: 'radial-gradient(#3b82f6 2px, transparent 2px)', backgroundSize: '24px 24px' }}></div>
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
