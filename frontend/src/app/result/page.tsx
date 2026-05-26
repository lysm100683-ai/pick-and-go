"use client";

import { useState, useEffect } from "react";
import { 
  Map, Calendar, Navigation, ArrowLeft, ExternalLink, RefreshCw, Database, 
  CreditCard, Mail, User, ShieldCheck, Ticket, CheckCircle2, AlertCircle, Loader2, Sparkles
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

declare global {
  interface Window {
    L: any;
  }
}

export default function ResultPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState(0);
  const [selectedDay, setSelectedDay] = useState("all");
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [apiData, setApiData] = useState<any>(null);
  const [userData, setUserData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 🎫 예약 프로세스 상태 변수
  const [isReservingModalOpen, setIsReservingModalOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentSubStep, setCurrentSubStep] = useState(0);
  const [userId, setUserId] = useState("user_traveler");
  const [email, setEmail] = useState("onboarding@resend.dev"); // Resend 샌드박스 기본 이메일
  const [paymentMethod, setPaymentMethod] = useState("card");
  const [reservationResult, setReservationResult] = useState<any>(null);
  const [reservationError, setReservationError] = useState<any>(null);

  // 🗺️ 지도 렌더링 상태 변수
  const [isLeafletLoaded, setIsLeafletLoaded] = useState(false);
  const [mapInstance, setMapInstance] = useState<any>(null);
  const [isRouteLoading, setIsRouteLoading] = useState(false);

  // 1. 초기 데이터 로드 (localStorage)
  useEffect(() => {
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

  // 2. Leaflet CSS 및 JS CDN 비동기 로드 (SSR 오류 방지용 브라우저 사이드 전용)
  useEffect(() => {
    if (window.L) {
      setIsLeafletLoaded(true);
      return;
    }

    // 1) Leaflet CSS 로드
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    link.integrity = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";
    link.crossOrigin = "";
    document.head.appendChild(link);

    // 2) Leaflet JS 로드
    const script = document.createElement("script");
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.integrity = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=";
    script.crossOrigin = "";
    script.async = true;
    script.onload = () => {
      setIsLeafletLoaded(true);
    };
    document.head.appendChild(script);

    return () => {
      if (document.head.contains(link)) document.head.removeChild(link);
      if (document.head.contains(script)) document.head.removeChild(script);
    };
  }, []);

  // 3. 실제 대화형 지도 초기화 및 마커 / 실제 도로 기반 동선 (OSRM) 렌더링
  useEffect(() => {
    if (!isLeafletLoaded || !apiData || !window.L) return;

    // 현재 렌더링할 플랜 획득
    const activePlan = apiData.plans[activeTab] || apiData.plans[0];
    if (!activePlan || !activePlan.days) return;

    const L = window.L;
    const container = document.getElementById("map-container");
    if (!container) return;

    // 기존 Leaflet 인스턴스 정리
    if (mapInstance) {
      mapInstance.remove();
    }

    // 맵 객체 생성
    const map = L.map("map-container", {
      zoomControl: true,
      scrollWheelZoom: true
    });

    // 🗺️ 모던한 CartoDB Voyager 타일 레이어 적용
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 20
    }).addTo(map);

    // 선택된 일차(Day)에 따른 장소 마커 리스트 필터링
    let placesToDraw: any[] = [];
    if (selectedDay === "all") {
      activePlan.days.forEach((dayObj: any) => {
        placesToDraw.push(...dayObj.places);
      });
    } else {
      const targetDay = activePlan.days.find((d: any) => d.day.toString() === selectedDay.toString());
      if (targetDay) {
        placesToDraw = targetDay.places;
      }
    }

    // 유효한 장소 좌표 목록
    const spotCoordinates = placesToDraw
      .filter((p: any) => p.lat && p.lng && p.lat !== 0 && p.lng !== 0)
      .map((p: any) => [parseFloat(p.lat), parseFloat(p.lng)]);

    // 비동기 도로 라우팅 경로 데이터 로드 및 그리기
    const renderRouteAndMarkers = async () => {
      if (spotCoordinates.length > 0) {
        // 모든 좌표가 포함되도록 영역 설정
        map.fitBounds(spotCoordinates, { padding: [50, 50] });

        let finalRouteCoords = spotCoordinates;

        // 🛣️ 2개 이상의 장소가 존재할 때 OSRM API를 호출하여 실제 도로 기준 경로선 획득
        if (spotCoordinates.length > 1) {
          setIsRouteLoading(true);
          const coordString = spotCoordinates.map(c => `${c[1]},${c[0]}`).join(';');
          // OSRM Driving Service
          const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${coordString}?overview=full&geometries=geojson`;
          
          try {
            const response = await fetch(osrmUrl);
            if (response.ok) {
              const routeData = await response.json();
              if (routeData.routes && routeData.routes.length > 0) {
                // OSRM은 [경도, 위도] 순으로 좌표를 주므로 [위도, 경도] 순으로 변환
                finalRouteCoords = routeData.routes[0].geometry.coordinates.map((c: any) => [c[1], c[0]]);
              }
            }
          } catch (err) {
            console.warn("OSRM 실제 도로 경로 호출 실패, 직선 경로로 대체합니다.", err);
          } finally {
            setIsRouteLoading(false);
          }
        }

        // 1) 🛣️ 실제 도로 경로 실선 그리기
        L.polyline(finalRouteCoords, {
          color: '#3b82f6', // 세련된 파란색
          weight: 5,
          opacity: 0.85,
          lineJoin: 'round'
        }).addTo(map);

        // 2) 번호가 박힌 커스텀 마커 배지 핀 생성
        placesToDraw.forEach((p: any, idx: number) => {
          if (!p.lat || !p.lng || p.lat === 0 || p.lng === 0) return;

          const numberIcon = L.divIcon({
            html: `<div style="
              background-color: #2563eb; 
              color: white; 
              border: 2px solid white; 
              border-radius: 50%; 
              width: 28px; 
              height: 28px; 
              display: flex; 
              align-items: center; 
              justify-content: center; 
              font-weight: 800; 
              font-size: 12px; 
              box-shadow: 0 4px 6px -1px rgba(0,0,0,0.15), 0 2px 4px -1px rgba(0,0,0,0.08);
            ">${idx + 1}</div>`,
            className: 'custom-map-badge',
            iconSize: [28, 28],
            iconAnchor: [14, 14]
          });

          const marker = L.marker([parseFloat(p.lat), parseFloat(p.lng)], { icon: numberIcon }).addTo(map);

          marker.bindPopup(`
            <div style="font-family: system-ui, sans-serif; padding: 4px; max-width: 200px;">
              <div style="font-size: 11px; font-weight: 800; color: #2563eb;">⏱️ ${p.time}</div>
              <strong style="font-size: 14px; color: #1e293b; display: block; margin-top: 2px;">${p.name}</strong>
              <span style="font-size: 10px; color: #64748b; background-color: #f1f5f9; padding: 1px 6px; border-radius: 4px; display: inline-block; margin-top: 4px;">${p.type}</span>
              <p style="font-size: 11px; margin: 6px 0 0 0; color: #475569; line-height: 1.4; border-top: 1px solid #f1f5f9; padding-top: 6px;">${p.desc}</p>
            </div>
          `);
        });
      } else {
        map.setView([33.3617, 126.5292], 10);
      }
    };

    renderRouteAndMarkers();
    setMapInstance(map);

    return () => {
      map.remove();
    };
  }, [isLeafletLoaded, apiData, activeTab, selectedDay]);

  const handleRegenerate = async () => {
    if (!userData) return;
    setIsRegenerating(true);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://pick-and-go-1.onrender.com";
      const res = await fetch(`${API_BASE}/api/v1/generate`, {
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
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://pick-and-go-1.onrender.com";
      const res = await fetch(`${API_BASE}/api/v1/update-db`, {
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

  // 🎫 5단계 예약 파이프라인 호출 함수
  const handleConfirmReservation = async () => {
    if (!userData || !apiData) return;
    
    setIsProcessing(true);
    setReservationError(null);
    setReservationResult(null);
    
    const activePlan = apiData.plans[activeTab] || apiData.plans[0];
    setCurrentSubStep(1); 
    
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://pick-and-go-1.onrender.com";
      
      const reservationPayload = {
        user_id: userId,
        user_email: email,
        itinerary_id: activePlan.theme,
        trip_data: activePlan,
        start_date: userData.start_date,
        end_date: userData.end_date,
        dest_city: userData.dest_city,
        dep_city: userData.dep_city,
        people: userData.people,
        payment: {
          method: paymentMethod,
          card_last4: "4242",
          budget_krw: userData.price_per_night_manwon * 10000 * (activePlan.days?.length || 1)
        }
      };

      const timer1 = setTimeout(() => setCurrentSubStep(2), 1200); 
      const timer2 = setTimeout(() => setCurrentSubStep(3), 2800); 
      const timer3 = setTimeout(() => setCurrentSubStep(4), 4200); 
      const timer4 = setTimeout(() => setCurrentSubStep(5), 5500); 

      const res = await fetch(`${API_BASE}/api/v1/reservation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reservationPayload),
      });

      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);

      const resultData = await res.json();
      
      if (!res.ok || resultData.status === "failed") {
        throw new Error(resultData.error_message || resultData.detail || "예약에 실패했습니다.");
      }

      setCurrentSubStep(5);
      await new Promise(r => setTimeout(r, 600)); 
      setReservationResult(resultData);
    } catch (e: any) {
      console.error(e);
      setReservationError(e.message || "예약 프로세스 중 내부 오류가 발생했습니다.");
    } finally {
      setIsProcessing(false);
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

      {/* ─── 🎫 5단계 예약 파이프라인 모달 ─── */}
      {isReservingModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
          <div className="w-full max-w-lg bg-white rounded-3xl shadow-2xl p-8 space-y-6 my-8">
            
            {/* 1단계: 입력 및 폼 화면 */}
            {!isProcessing && !reservationResult && !reservationError && (
              <div className="space-y-6">
                <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
                  <div className="w-12 h-12 bg-blue-100 rounded-2xl flex items-center justify-center text-blue-600">
                    <Ticket className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-slate-800">전체 패키지 실시간 예약</h3>
                    <p className="text-sm text-slate-500">일정 내 항공편 + 숙소 + 명소 통합 즉시 결제</p>
                  </div>
                </div>

                {/* 상품 요약 정보 */}
                <div className="p-4 bg-blue-50/60 rounded-2xl border border-blue-100 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500 font-medium">여정 테마</span>
                    <span className="text-slate-800 font-bold">{activePlan.theme}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500 font-medium">여행 일정</span>
                    <span className="text-slate-800 font-bold">{userData.start_date} ~ {userData.end_date}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500 font-medium">여행 인원</span>
                    <span className="text-slate-800 font-bold">{userData.people}명</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500 font-medium">목적지</span>
                    <span className="text-slate-800 font-bold">{userData.dep_city} ➡️ {userData.dest_city}</span>
                  </div>
                </div>

                {/* 입력 폼 */}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-600 flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5" /> 예약자 성함 (ID)
                    </label>
                    <input 
                      type="text" 
                      value={userId} 
                      onChange={(e) => setUserId(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500" 
                      placeholder="예약자명을 적어주세요"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-600 flex items-center gap-1.5">
                      <Mail className="w-3.5 h-3.5" /> 티켓 수신 이메일 주소
                    </label>
                    <input 
                      type="email" 
                      value={email} 
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500" 
                      placeholder="E-Ticket을 받을 이메일을 적어주세요"
                    />
                    <p className="text-[11px] text-slate-400 font-medium">※ Resend API Sandbox 연동 중으로 실발송 성공을 보장합니다.</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-600 flex items-center gap-1.5">
                      <CreditCard className="w-3.5 h-3.5" /> 모의 결제 방식
                    </label>
                    <div className="flex gap-3 p-1 bg-slate-100 rounded-xl border border-slate-200">
                      <button 
                        type="button" 
                        onClick={() => setPaymentMethod("card")}
                        className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
                          paymentMethod === "card" ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'
                        }`}
                      >
                        신용카드 자동승인
                      </button>
                      <button 
                        type="button" 
                        onClick={() => setPaymentMethod("transfer")}
                        className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
                          paymentMethod === "transfer" ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'
                        }`}
                      >
                        가상계좌 모의이체
                      </button>
                    </div>
                  </div>
                </div>

                {/* 동작 실행 버튼 */}
                <div className="flex gap-3 pt-4">
                  <button 
                    onClick={() => setIsReservingModalOpen(false)}
                    className="flex-1 py-3 text-sm font-bold text-slate-500 hover:text-slate-800 bg-slate-50 hover:bg-slate-100 rounded-xl transition-colors border border-slate-200"
                  >
                    창 닫기
                  </button>
                  <button 
                    onClick={handleConfirmReservation}
                    className="flex-1 py-3 text-sm font-black text-white bg-blue-600 hover:bg-blue-500 rounded-xl transition-colors shadow-lg shadow-blue-500/20"
                  >
                    💳 결제 및 예약 확정
                  </button>
                </div>
              </div>
            )}

            {/* 2단계: 실시간 5단계 파이프라인 진행 상태 (로더) */}
            {isProcessing && (
              <div className="space-y-8 py-6 text-center">
                <div className="relative inline-flex items-center justify-center">
                  <Loader2 className="w-16 h-16 text-blue-500 animate-spin" />
                  <Sparkles className="w-6 h-6 text-amber-400 absolute animate-pulse" />
                </div>
                
                <div className="space-y-2">
                  <h4 className="text-xl font-bold text-slate-800">통합 패키지 실시간 예약 중</h4>
                  <p className="text-sm text-slate-500">Saga Rollback 트랜잭션 안전성 설계가 적용되어 안전합니다.</p>
                </div>

                {/* 5단계 비주얼 스테퍼 */}
                <div className="space-y-4 max-w-sm mx-auto text-left">
                  {[
                    { step: 1, name: "Sub1: 예약 정합성 및 중복 체크 검증" },
                    { step: 2, name: "Sub2: 항공(Duffel) + 숙소(LiteAPI) 병렬 결제 시도" },
                    { step: 3, name: "Sub3: 파트너사 확정 상태 실시간 상호 대조 검증" },
                    { step: 4, name: "Sub4: Supabase PostgreSQL 트랜잭션 내역 저장" },
                    { step: 5, name: "Sub5: 티켓 메일 발송 (Resend API) 및 알림 안내" }
                  ].map((s) => (
                    <div key={s.step} className="flex items-center gap-3">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-black
                        ${currentSubStep > s.step 
                          ? 'bg-emerald-500 text-white' 
                          : currentSubStep === s.step 
                            ? 'bg-blue-500 text-white animate-pulse' 
                            : 'bg-slate-100 text-slate-400'}`}>
                        {currentSubStep > s.step ? "✓" : s.step}
                      </div>
                      <span className={`text-xs font-semibold
                        ${currentSubStep === s.step ? 'text-blue-600 font-bold' : currentSubStep > s.step ? 'text-slate-700' : 'text-slate-400'}`}>
                        {s.name}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 3단계: 예약 최종 성공 카드 */}
            {!isProcessing && reservationResult && (
              <div className="space-y-6">
                <div className="text-center space-y-3">
                  <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/10 ring-8 ring-emerald-50">
                    <CheckCircle2 className="w-10 h-10" />
                  </div>
                  <h3 className="text-2xl font-black text-slate-800">예약 패키지 최종 확정!</h3>
                  <p className="text-sm text-slate-500">모든 통합 일정이 성공적으로 결제 및 발권되었습니다.</p>
                </div>

                {/* 티켓 디테일 영수증 스타일 */}
                <div className="border border-dashed border-slate-200 rounded-2xl p-5 bg-slate-50 relative overflow-hidden space-y-4">
                  {/* 사이드 펀칭 데코 */}
                  <div className="absolute -left-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white border border-slate-200"></div>
                  <div className="absolute -right-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white border border-slate-200"></div>

                  <div className="flex justify-between text-xs pb-3 border-b border-slate-200 font-mono">
                    <span className="text-slate-400">RESERVATION ID</span>
                    <span className="text-slate-800 font-bold">{reservationResult.reservation_id}</span>
                  </div>

                  <div className="space-y-2 text-sm pt-1">
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-semibold">총 결제 승인액</span>
                      <span className="text-blue-700 font-black">
                        {reservationResult.total_amount?.toLocaleString()} {reservationResult.currency || 'KRW'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-semibold">티켓 수령 이메일</span>
                      <span className="text-slate-800 font-bold">{email}</span>
                    </div>
                  </div>

                  {/* 세부 파트너 결과 */}
                  <div className="pt-3 border-t border-slate-200 space-y-2">
                    <h5 className="text-xs font-bold text-slate-700">예약 항목별 결과현황:</h5>
                    {reservationResult.items?.map((item: any, idx: number) => (
                      <div key={idx} className="flex justify-between text-xs bg-white p-2.5 rounded-lg border border-slate-100">
                        <span className="font-semibold text-slate-600">
                          {item.item_type === 'flight' ? '✈️ 항공 예약' : '🏨 숙박 예약'}
                        </span>
                        <div className="text-right">
                          <span className="px-2 py-0.5 bg-emerald-50 border border-emerald-100 text-emerald-600 rounded text-[10px] font-bold">
                            확정완료 ({item.partner_booking_id || 'BOOKED'})
                          </span>
                          <div className="text-[9px] text-slate-400 mt-0.5">{item.partner_name}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="p-4 bg-emerald-50 border border-emerald-100 rounded-xl flex items-start gap-2.5">
                    <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                    <p className="text-xs text-emerald-700 leading-relaxed font-semibold">
                      **티켓 발송 완료**: 입력하신 이메일({email})로 항공권 바우처와 호텔 예약 증명서가 즉시 발송되었습니다. 메일 수신함을 확인해 보세요!
                    </p>
                  </div>

                  <button 
                    onClick={() => {
                      setIsReservingModalOpen(false);
                      setReservationResult(null);
                    }}
                    className="w-full py-4 text-sm font-black text-white bg-blue-600 hover:bg-blue-500 rounded-2xl transition-all shadow-lg shadow-blue-500/20"
                  >
                    예약 프로세스 완료 확인
                  </button>
                </div>
              </div>
            )}

            {/* 4단계: 에러/실패 카드 */}
            {!isProcessing && reservationError && (
              <div className="space-y-6">
                <div className="text-center space-y-3">
                  <div className="w-16 h-16 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mx-auto shadow-lg shadow-rose-500/10 ring-8 ring-rose-50">
                    <AlertCircle className="w-10 h-10" />
                  </div>
                  <h3 className="text-xl font-bold text-slate-800">예약 중 오류가 발생했습니다</h3>
                  <p className="text-sm text-slate-500">통합 결제 처리 중 백엔드 트랜잭션 에러 발생</p>
                </div>

                <div className="p-4 bg-rose-50 border border-rose-100 rounded-2xl text-xs text-rose-700 leading-relaxed font-semibold font-mono">
                  {reservationError}
                </div>

                <div className="p-4 bg-slate-50 rounded-2xl space-y-2 border border-slate-100 text-xs text-slate-500 leading-relaxed font-medium">
                  <strong>💡 안전 복구(Rollback) 완료</strong>: Pick & Go Saga 매니저에 의해 이미 처리된 일부 모의 승인 항목(예: 항공권 등)에 대해 롤백 취소 명령이 자동 하달되어 안전한 원상복구가 완료되었습니다.
                </div>

                <div className="flex gap-3">
                  <button 
                    onClick={() => {
                      setReservationError(null);
                    }}
                    className="flex-1 py-3 text-sm font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
                  >
                    다시 시도하기
                  </button>
                  <button 
                    onClick={() => {
                      setIsReservingModalOpen(false);
                      setReservationError(null);
                    }}
                    className="flex-1 py-3 text-sm font-bold text-white bg-blue-600 hover:bg-blue-500 rounded-xl transition-colors"
                  >
                    창 닫기
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      )}

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
            <button 
              onClick={handleUpdateDB}
              className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-slate-50 text-slate-700 text-sm font-medium rounded-xl transition-colors border border-slate-200 shadow-sm"
            >
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

        {/* 🚀 premium 패키지 통합 예약 및 결제 CTA 영역 */}
        <div className="bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-600 rounded-3xl p-6 md:p-8 text-white shadow-xl shadow-blue-500/20 mb-8 flex flex-col md:flex-row items-center justify-between gap-6 relative overflow-hidden border border-white/10">
          <div className="absolute -right-12 -bottom-12 w-48 h-48 bg-white/5 rounded-full blur-2xl"></div>
          <div className="space-y-2 relative z-10">
            <span className="px-2.5 py-0.5 bg-white/20 text-white rounded text-[10px] font-black uppercase tracking-widest border border-white/20">Saga Transaction</span>
            <h3 className="text-2xl font-black mb-1 flex items-center gap-2">🎫 이 패키지 일정 전체 한방에 예약하기</h3>
            <p className="text-blue-100 text-sm font-semibold max-w-2xl leading-relaxed">
              본 일정의 추천 항공권 + 4성급 호텔 숙소 + 주요 동선 명소 통합 예약 결제를 5단계 파이프라인을 통해 실시간으로 안전하게 처리합니다.
            </p>
          </div>
          <button 
            onClick={() => setIsReservingModalOpen(true)}
            className="shrink-0 relative z-10 px-8 py-4 bg-white hover:bg-slate-50 text-blue-700 font-black text-lg rounded-2xl shadow-lg transition-transform hover:-translate-y-0.5 active:translate-y-0"
          >
            실시간 예약 결제하기
          </button>
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
                        {/* 영업 상태 경고 배지 — staleness_warning 필드 기반 */}
                        {place.staleness_warning === 'danger' && (
                          <span
                            title="방문 전 영업 여부를 반드시 확인하세요. 장기간 정보가 업데이트되지 않았습니다."
                            className="flex items-center gap-1 px-2 py-0.5 bg-red-50 border border-red-200 text-red-600 rounded-md text-xs font-semibold"
                          >
                            🔴 영업 확인 필요
                          </span>
                        )}
                        {place.staleness_warning === 'caution' && (
                          <span
                            title="정보가 6개월 이상 갱신되지 않았습니다. 방문 전 확인을 권장합니다."
                            className="flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-600 rounded-md text-xs font-semibold"
                          >
                            🟡 정보 확인 권장
                          </span>
                        )}
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
              
              {/* 🗺️ 실제 로딩 완료된 Leaflet 맵 컨테이너 탑재 */}
              <div 
                id="map-container" 
                className="w-full h-[600px] bg-slate-50 rounded-3xl border border-slate-200 overflow-hidden relative shadow-xl shadow-slate-200/50 z-0"
              >
                {(isRouteLoading || !isLeafletLoaded) && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/70 z-10">
                    <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-3" />
                    <p className="text-sm font-bold text-slate-500">
                      {!isLeafletLoaded ? '대화형 지도 엔진 초기화 중...' : '🛣️ 실제 도로 경로 실시간 탐색 중...'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
