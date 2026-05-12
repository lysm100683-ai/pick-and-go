"use client";

import { useState } from "react";
import { Plane, Calendar, Users, MapPin, Wallet, Compass, Car, Home as HomeIcon, Camera, Utensils, Briefcase, Info, Sparkles } from "lucide-react";
import { format, addDays } from "date-fns";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  const [formData, setFormData] = useState({
    // Step 1
    dep_city: "서울/인천",
    dest_city: "제주",
    start_date: format(addDays(new Date(), 7), "yyyy-MM-dd"),
    end_date: format(addDays(new Date(), 13), "yyyy-MM-dd"),
    people: 2,
    companions: ["가족"],
    budget_level: "중",

    // Step 2
    style: ["휴양", "관광"],
    transport: ["항공"],
    pace: "보통",
    local_transport: "자차",

    // Step 3
    lodging_types: ["호텔"],
    star_rating: 4,
    price_per_night_manwon: 20,
    num_hotels: 1,

    // Step 4 (음식 및 알러지 - 새로 추가된 세부 조건)
    food_prefs: [] as string[],
    food_allergy_text: "",
    with_kids: false,
    stroller: false,
    barrier_free: false,
    photo_spot: false,

    // Advanced (항공/수하물/기타)
    seat_pref: "무관",
    baggage: "기내만",
    keywords: "",
    english_ok: false,
    walk_minutes: 45,
    crowd_avoid: "보통",
    temp_range: [15, 25],
    rainy_ok: false,
    time_constraints: "",
    max_transfers: 1,
    visa_free: false,

    // Step 5: 추가 입력형 조건 (입력형 20개 달성)
    trip_purpose: "",
    preferred_airline: "",
    arrival_time_pref: "",
    departure_time_pref: "",
    interest_places: "",
    daily_budget_manwon: 30,
    notes: "",
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg]         = useState("");
  const [genTime, setGenTime]           = useState<string | null>(null);

  const handleChange = (e: any) => {
    const { name, value, type, checked } = e.target;
    setFormData({
      ...formData,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const handleArrayChange = (name: string, value: string) => {
    setFormData((prev: any) => {
      const current = prev[name];
      const updated = current.includes(value)
        ? current.filter((item: string) => item !== value)
        : [...current, value];
      return { ...prev, [name]: updated };
    });
  };

  const handleSubmit = async (e: any) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg("");
    
    try {
      const res = await fetch("https://pick-and-go-1.onrender.com/api/v1/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `서버 에러 (${res.status})`);
      }

      const data = await res.json();
      // 응답 헤더에서 생성 시간 읽기 (≤5초 목표 사양 검증)
      const t = res.headers.get("X-Generation-Time");
      if (t) setGenTime(t);

      localStorage.setItem("api_result", JSON.stringify(data));
      localStorage.setItem("form_data",  JSON.stringify(formData));

      router.push("/result");
      
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "일정 생성 중 오류가 발생했습니다.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-sky-50 text-slate-800 font-sans selection:bg-blue-200">
      {/* 화사한 배경 그라데이션 */}
      <div className="fixed inset-0 -z-10 bg-gradient-to-br from-blue-50 via-white to-sky-100"></div>
      
      {/* 장식용 패턴 (구름 느낌의 부드러운 형태) */}
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none opacity-40">
        <div className="absolute -top-[20%] -right-[10%] w-[70%] h-[70%] rounded-full bg-blue-200/50 blur-3xl"></div>
        <div className="absolute top-[40%] -left-[20%] w-[60%] h-[60%] rounded-full bg-emerald-100/40 blur-3xl"></div>
        <div className="absolute -bottom-[20%] right-[10%] w-[50%] h-[50%] rounded-full bg-purple-100/50 blur-3xl"></div>
      </div>

      <main className="max-w-4xl mx-auto px-4 py-12 sm:px-6 lg:px-8 relative">
        
        {/* Header */}
        <div className="text-center mb-12 space-y-4">
          <div className="inline-flex items-center justify-center p-4 bg-white rounded-3xl shadow-xl shadow-blue-500/10 mb-4 ring-1 ring-slate-100 transform -rotate-3 hover:rotate-0 transition-transform duration-300">
            <Plane className="w-10 h-10 text-blue-500 fill-blue-500" />
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-slate-800">
            Pick & Go <span className="text-blue-500">Travel</span>
          </h1>
          <p className="text-lg text-slate-500 max-w-2xl mx-auto font-medium">
            AI가 분석하는 완벽한 맞춤형 여행 일정. 당신만의 아주 디테일한 여행 취향을 알려주세요.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          
          {/* Section 1: Basic Info */}
          <section className="bg-white/70 backdrop-blur-xl border border-white rounded-3xl p-6 md:p-8 shadow-xl shadow-slate-200/50 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-blue-100 rounded-full blur-3xl -z-10 translate-x-1/2 -translate-y-1/2"></div>
            <h2 className="text-2xl font-bold flex items-center gap-3 mb-6 text-slate-800">
              <MapPin className="w-6 h-6 text-blue-500" /> 1. 어디로, 언제 떠나시나요?
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700">출발 도시</label>
                <input type="text" name="dep_city" value={formData.dep_city} onChange={handleChange} 
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all text-slate-700" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-1">
                  목적지 도시 <Sparkles className="w-3 h-3 text-amber-400" />
                </label>
                <input type="text" name="dest_city" value={formData.dest_city} onChange={handleChange} 
                  className="w-full bg-white border-2 border-blue-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-800 font-bold shadow-sm" />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-blue-500" /> 출발일
                </label>
                <input type="date" name="start_date" value={formData.start_date} onChange={handleChange} 
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-700 font-medium" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-blue-500" /> 종료일
                </label>
                <input type="date" name="end_date" value={formData.end_date} onChange={handleChange} 
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-700 font-medium" />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Users className="w-4 h-4 text-emerald-500" /> 인원수
                </label>
                <input type="number" name="people" min="1" max="20" value={formData.people} onChange={handleChange} 
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-slate-700" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Wallet className="w-4 h-4 text-emerald-500" /> 1인당 예산 수준
                </label>
                <select name="budget_level" value={formData.budget_level} onChange={handleChange} 
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-slate-700 font-medium">
                  <option value="저">가성비 숙소와 식사 중심 (저)</option>
                  <option value="중">표준적인 여행 경비 (중)</option>
                  <option value="고">고급 호텔과 파인 다이닝 (고)</option>
                </select>
              </div>
            </div>
            
            <div className="mt-6 space-y-3 p-4 bg-emerald-50/50 rounded-2xl border border-emerald-100">
              <label className="text-sm font-bold text-emerald-800">누구와 함께 가시나요?</label>
              <div className="flex flex-wrap gap-2">
                {["가족", "커플", "친구", "나홀로", "부모님 동반", "아이 동반", "반려동물"].map(comp => (
                  <button key={comp} type="button" onClick={() => handleArrayChange("companions", comp)}
                    className={`px-4 py-2 rounded-full text-sm font-semibold transition-all duration-200 border 
                      ${formData.companions.includes(comp) 
                        ? 'bg-emerald-500 text-white border-emerald-500 shadow-md shadow-emerald-500/30' 
                        : 'bg-white text-slate-600 border-slate-200 hover:border-emerald-300 hover:text-emerald-700 hover:bg-emerald-50'}`}>
                    {comp}
                  </button>
                ))}
              </div>
            </div>
          </section>

          {/* Section 2: Preferences */}
          <section className="bg-white/80 backdrop-blur-xl border border-white rounded-3xl p-6 md:p-8 shadow-xl shadow-slate-200/50">
            <h2 className="text-2xl font-bold flex items-center gap-3 mb-6 text-slate-800">
              <Compass className="w-6 h-6 text-purple-500" /> 2. 여행을 어떻게 채우고 싶나요?
            </h2>

            <div className="space-y-8">
              <div className="space-y-3">
                <label className="text-sm font-bold text-slate-700">이번 여행의 핵심 테마 (다중 선택 가능)</label>
                <div className="flex flex-wrap gap-2">
                  {["휴양", "관광", "맛집", "쇼핑", "액티비티", "자연풍경", "역사/문화", "카페투어", "호캉스"].map(s => (
                    <button key={s} type="button" onClick={() => handleArrayChange("style", s)}
                      className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 border 
                        ${formData.style.includes(s) 
                          ? 'bg-purple-500 text-white border-purple-500 shadow-lg shadow-purple-500/30 -translate-y-0.5' 
                          : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-purple-300 hover:shadow-md'}`}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-3">
                  <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    <Car className="w-4 h-4 text-purple-500" /> 현지 이동 수단
                  </label>
                  <div className="flex p-1 bg-slate-100 rounded-xl border border-slate-200">
                    {["렌트카", "자차", "대중교통", "택시위주"].map(t => (
                      <button key={t} type="button" onClick={() => setFormData({...formData, local_transport: t})}
                        className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-all ${
                          formData.local_transport === t ? 'bg-white text-purple-700 shadow-sm border border-slate-200' : 'text-slate-500 hover:text-slate-800'
                        }`}>
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-sm font-semibold text-slate-700">일정은 어느 정도로 짤까요?</label>
                  <div className="flex p-1 bg-slate-100 rounded-xl border border-slate-200">
                    {["여유롭게 (1일 1~2곳)", "보통 (1일 3~4곳)", "알차게 (1일 5곳 이상)"].map(p => {
                      const value = p.split(' ')[0]; // "여유롭게", "보통", "알차게" -> 백엔드가 보통, 여유 등을 파싱
                      return (
                        <button key={value} type="button" onClick={() => setFormData({...formData, pace: value})}
                          className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-all ${
                            formData.pace === value ? 'bg-white text-purple-700 shadow-sm border border-slate-200' : 'text-slate-500 hover:text-slate-800'
                          }`}>
                          {p}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Section 3: Lodging & Transport Details */}
          <section className="bg-white/80 backdrop-blur-xl border border-white rounded-3xl p-6 md:p-8 shadow-xl shadow-slate-200/50">
            <h2 className="text-2xl font-bold flex items-center gap-3 mb-6 text-slate-800">
              <Briefcase className="w-6 h-6 text-indigo-500" /> 3. 비행기 및 숙소 세부 조건
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <div className="space-y-2 lg:col-span-2">
                <label className="text-sm font-semibold text-slate-700">원하시는 숙소 형태</label>
                <div className="flex flex-wrap gap-2">
                  {["호텔", "리조트", "펜션/풀빌라", "게스트하우스", "에어비앤비"].map(t => (
                    <button key={t} type="button" onClick={() => handleArrayChange("lodging_types", t)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 border 
                        ${formData.lodging_types.includes(t) 
                          ? 'bg-indigo-100 text-indigo-700 border-indigo-200' 
                          : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-200'}`}>
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700">최소 별점</label>
                <select name="star_rating" value={formData.star_rating} onChange={handleChange} 
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 text-slate-700 font-medium">
                  <option value="3">⭐⭐⭐ 3성급 이상</option>
                  <option value="4">⭐⭐⭐⭐ 4성급 이상</option>
                  <option value="5">⭐⭐⭐⭐⭐ 5성급 럭셔리</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700">전체 여행 중 숙소 변경</label>
                <select name="num_hotels" value={formData.num_hotels} onChange={handleChange} 
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 text-slate-700 font-medium">
                  <option value="1">1개 숙소만 이용</option>
                  <option value="2">2곳에서 숙박</option>
                  <option value="3">매일 다른 숙소 (이동 최소화)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-6 border-t border-slate-100">
               <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Plane className="w-4 h-4 text-indigo-400" /> 좌석 등급
                </label>
                <select name="seat_pref" value={formData.seat_pref} onChange={handleChange} 
                  className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700">
                  <option value="무관">상관 없음 (가장 저렴한 순)</option>
                  <option value="이코노미">이코노미 클래스</option>
                  <option value="프리미엄 이코노미">프리미엄 이코노미</option>
                  <option value="비즈니스">비즈니스 클래스</option>
                  <option value="일등석">일등석 (First Class)</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Briefcase className="w-4 h-4 text-indigo-400" /> 수하물 옵션
                </label>
                <select name="baggage" value={formData.baggage} onChange={handleChange} 
                  className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700">
                  <option value="기내만">기내 수하물만 (수하물 없음)</option>
                  <option value="위탁 15kg">위탁 수하물 15kg 기본</option>
                  <option value="위탁 23kg 이상">위탁 수하물 23kg 이상 여유롭게</option>
                  <option value="특수 수하물">특수 수하물 (골프백, 다이빙 장비 등)</option>
                </select>
              </div>
            </div>
          </section>

          {/* Section 4: Dietary & Special */}
          <section className="bg-white/80 backdrop-blur-xl border border-white rounded-3xl p-6 md:p-8 shadow-xl shadow-slate-200/50">
            <h2 className="text-2xl font-bold flex items-center gap-3 mb-6 text-slate-800">
              <Utensils className="w-6 h-6 text-rose-500" /> 4. 식단 및 인생사진 등 추가 요청
            </h2>

            <div className="mb-6 space-y-3">
              <label className="text-sm font-bold text-slate-700">식이 요법 및 선호 식단 (다중 선택)</label>
              <div className="flex flex-wrap gap-2">
                {["제한 없음", "육류 위주", "해산물 매니아", "채식(비건)", "할랄식", "로컬 길거리음식", "미슐랭/파인다이닝"].map(f => (
                  <button key={f} type="button" onClick={() => handleArrayChange("food_prefs", f)}
                    className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 border 
                      ${formData.food_prefs.includes(f) 
                        ? 'bg-rose-500 text-white border-rose-500 shadow-md shadow-rose-500/30' 
                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-rose-300'}`}>
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-8 space-y-2">
              <label className="text-sm font-semibold text-slate-700">알러지 또는 못 드시는 음식 (선택사항)</label>
              <input type="text" name="food_allergy_text" value={formData.food_allergy_text} onChange={handleChange}
                maxLength={1000}
                placeholder="예: 땅콩 알러지, 고수 빼주세요, 갑각류 알러지가 있어요"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-500 text-slate-700 placeholder-slate-400" />
            </div>

            <div className="p-5 bg-rose-50/50 border border-rose-100 rounded-2xl">
              <label className="text-sm font-bold text-rose-800 mb-4 block">동행자 맞춤 및 특별 시설 요구사항</label>
              <div className="flex flex-wrap gap-4">
                <label className="flex items-center gap-3 cursor-pointer group bg-white px-4 py-2.5 rounded-xl shadow-sm border border-slate-100 hover:border-rose-200 transition-colors">
                  <div className="relative flex items-center">
                    <input type="checkbox" name="barrier_free" checked={formData.barrier_free} onChange={handleChange} className="peer sr-only" />
                    <div className="w-5 h-5 bg-slate-100 border border-slate-300 rounded transition-colors peer-checked:bg-rose-500 peer-checked:border-rose-500 flex items-center justify-center">
                      <svg className="w-3.5 h-3.5 text-white opacity-0 peer-checked:opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path></svg>
                    </div>
                  </div>
                  <span className="text-slate-700 font-medium group-hover:text-rose-600 text-sm">♿ 휠체어 전용 시설 (Barrier Free)</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer group bg-white px-4 py-2.5 rounded-xl shadow-sm border border-slate-100 hover:border-rose-200 transition-colors">
                  <div className="relative flex items-center">
                    <input type="checkbox" name="stroller" checked={formData.stroller} onChange={handleChange} className="peer sr-only" />
                    <div className="w-5 h-5 bg-slate-100 border border-slate-300 rounded transition-colors peer-checked:bg-orange-500 peer-checked:border-orange-500 flex items-center justify-center">
                      <svg className="w-3.5 h-3.5 text-white opacity-0 peer-checked:opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path></svg>
                    </div>
                  </div>
                  <span className="text-slate-700 font-medium group-hover:text-orange-600 text-sm">🍼 유모차 사용 가능한 평지 위주</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer group bg-white px-4 py-2.5 rounded-xl shadow-sm border border-slate-100 hover:border-rose-200 transition-colors">
                  <div className="relative flex items-center">
                    <input type="checkbox" name="photo_spot" checked={formData.photo_spot} onChange={handleChange} className="peer sr-only" />
                    <div className="w-5 h-5 bg-slate-100 border border-slate-300 rounded transition-colors peer-checked:bg-pink-500 peer-checked:border-pink-500 flex items-center justify-center">
                      <svg className="w-3.5 h-3.5 text-white opacity-0 peer-checked:opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path></svg>
                    </div>
                  </div>
                  <span className="text-slate-700 font-medium group-hover:text-pink-600 text-sm">📸 숨겨진 사진 명소 포함</span>
                </label>
              </div>
            </div>
            
            <div className="mt-8 space-y-2">
              <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                <Info className="w-4 h-4 text-slate-400" /> 기타 특별하게 원하시는 액티비티나 요구사항을 자유롭게 적어주세요.
              </label>
              <textarea name="keywords" value={formData.keywords} onChange={handleChange}
                maxLength={1000}
                rows={3} placeholder="예: 첫날엔 무조건 스쿠버다이빙, 부모님 생신 기념이라 프라이빗 요트 투어를 원해요."
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-500 text-slate-700 placeholder-slate-400 resize-none break-keep" />
            </div>

          </section>

          {/* Section 5: Additional Requests */}
          <section className="bg-white/80 backdrop-blur-xl border border-white rounded-3xl p-6 md:p-8 shadow-xl shadow-slate-200/50">
            <h2 className="text-2xl font-bold flex items-center gap-3 mb-6 text-slate-800">
              <Info className="w-6 h-6 text-teal-500" /> 5. 추가 요청 사항
            </h2>
            <p className="text-sm text-slate-500 mb-6">입력형 조건 20개 효주 상세 항목입니다. 선택 사항이지만 더 정확한 일정 생성에 도움이 됩니다.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700">✈️ 여행 목적 / 테마</label>
                <input type="text" name="trip_purpose"
                  value={formData.trip_purpose} onChange={handleChange}
                  placeholder="예) 신혼여행, 가족 추억 여행, 소울리쳐"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-teal-500 text-slate-700 placeholder-slate-400" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700">항공기 선호 항공사</label>
                <input type="text" name="preferred_airline"
                  value={formData.preferred_airline} onChange={handleChange}
                  placeholder="예) 대한항공, 아시아나 (없으면 빈칸)"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-teal-500 text-slate-700 placeholder-slate-400" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700">🕒 도착 희망 시간대</label>
                <input type="text" name="arrival_time_pref"
                  value={formData.arrival_time_pref} onChange={handleChange}
                  placeholder="예) 오전 10시 이전"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-teal-500 text-slate-700 placeholder-slate-400" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700">🕒 출발 희망 시간대</label>
                <input type="text" name="departure_time_pref"
                  value={formData.departure_time_pref} onChange={handleChange}
                  placeholder="예) 오후 3시 이후"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-teal-500 text-slate-700 placeholder-slate-400" />
              </div>
            </div>
            <div className="space-y-2 mb-6">
              <label className="text-sm font-semibold text-slate-700">📍 꼭 가보고 싶은 장소 / 명소</label>
              <input type="text" name="interest_places"
                value={formData.interest_places} onChange={handleChange}
                maxLength={500}
                placeholder="예) 성산일출, 하쏼이 인구여, OO 맛집 거리"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-teal-500 text-slate-700 placeholder-slate-400" />
            </div>
            <div className="space-y-2 mb-6">
              <label className="text-sm font-semibold text-slate-700">💰 하루 자유 예산 (만원, 숙소 제외)</label>
              <input type="number" name="daily_budget_manwon"
                value={formData.daily_budget_manwon}
                onChange={handleChange}
                min={1} max={500}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-teal-500 text-slate-700" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-700">📝 기타 특이사항 또는 요청사항</label>
              <textarea name="notes"
                value={formData.notes} onChange={handleChange}
                maxLength={1000} rows={3}
                placeholder="예) 휴스 차항이 있어 무리하지 않은 일정으로 짜주세요"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-teal-500 text-slate-700 placeholder-slate-400 resize-none" />
            </div>
          </section>
          <button type="submit" disabled={isSubmitting}
            className="w-full relative group overflow-hidden rounded-2xl bg-blue-600 p-1 transition-all hover:shadow-2xl hover:shadow-blue-500/40 transform hover:-translate-y-1">
            <div className="relative px-8 py-5 bg-white/10 backdrop-blur-sm rounded-[12px] flex items-center justify-center gap-3">
              {isSubmitting ? (
                <div className="w-6 h-6 border-3 border-white/30 border-t-white rounded-full animate-spin"></div>
              ) : (
                <Plane className="w-6 h-6 text-white group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
              )}
              <span className="text-xl font-bold text-white tracking-wide">
                {isSubmitting ? "AI가 맞춤 여행 일정을 생성하고 있습니다..." : "완벽한 여행 일정 만들기"}
              </span>
            </div>
          </button>
          
          {genTime && (
            <div className="flex items-center justify-center gap-2 text-sm text-emerald-700 font-semibold bg-emerald-50 border border-emerald-200 rounded-xl p-3">
              <span>✅ 일정 생성 완료 — 소요 시간: <strong>{genTime}</strong></span>
              <span className="text-emerald-500">{parseFloat(genTime) <= 5 ? "(목표 ≤5초 충족 ✓)" : "(목표 ≤5초 초과 ⚠️)"}</span>
            </div>
          )}

          {errorMsg && (
            <div className="text-center text-red-500 font-medium p-3 bg-red-50 rounded-xl border border-red-200">
              {errorMsg}
            </div>
          )}

        </form>
      </main>
    </div>
  );
}
