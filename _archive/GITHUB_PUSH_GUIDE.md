# 📤 GitHub에 코드 올리기 가이드

## 현재 상태
- **브랜치**: `shkim228-patch-1`
- **상태**: 로컬에 6개의 커밋이 있고, 추가 변경사항이 있음

## 🚀 GitHub에 올리는 방법

### 1단계: 변경된 파일 추가하기
```powershell
# 프로젝트 폴더로 이동
cd c:\projects\pick-and-go

# 모든 변경사항 확인
git status

# 모든 변경사항을 스테이징 영역에 추가
git add .
```

### 2단계: 커밋 메시지 작성하기
```powershell
git commit -m "PostgreSQL + PostGIS 통합 완료 - Phase 1 구현"
```

### 3단계: GitHub에 푸시하기
```powershell
# 현재 브랜치(shkim228-patch-1)에 푸시
git push origin shkim228-patch-1
```

## 📝 전체 명령어 (한 번에 복사해서 실행)
```powershell
cd c:\projects\pick-and-go
git add .
git commit -m "PostgreSQL + PostGIS 통합 완료 - Phase 1 구현"
git push origin shkim228-patch-1
```

## ⚠️ 주의사항

### 만약 푸시가 거부된다면
```powershell
# 원격 저장소의 최신 변경사항을 먼저 가져오기
git pull origin shkim228-patch-1

# 충돌이 있다면 해결 후 다시 푸시
git push origin shkim228-patch-1
```

### 다른 브랜치로 푸시하고 싶다면
```powershell
# main 브랜치로 전환
git checkout main

# 현재 브랜치의 변경사항을 main에 병합
git merge shkim228-patch-1

# main 브랜치에 푸시
git push origin main
```

## 🔍 유용한 Git 명령어

```powershell
# 현재 상태 확인
git status

# 변경 이력 확인
git log --oneline -10

# 어떤 브랜치에 있는지 확인
git branch

# 변경된 파일 내용 확인
git diff
```

## 📚 Git 용어 설명

- **브랜치(Branch)**: 코드의 독립적인 작업 공간
- **커밋(Commit)**: 변경사항을 저장하는 것
- **푸시(Push)**: 로컬 변경사항을 GitHub에 업로드
- **풀(Pull)**: GitHub의 최신 변경사항을 로컬로 다운로드
- **스테이징(Staging)**: 커밋할 파일을 선택하는 과정
