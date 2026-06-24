from mcp.server.fastmcp import FastMCP
import json
import os
from typing import Dict, Any

# 1. MCP 이름 설정
mcp = FastMCP("Portfolio-Assistant")

# 2. Components DataBase
COMPONENTS_DB = {
    "common": [
        {"id": "section", "name": "Section", "category": "layout", "desc": "포트폴리오 구획을 나누는 컨테이너"},
        {"id": "columns", "name": "Columns", "category": "layout", "desc": "2단/3단 레이아웃 구성"},
        {"id": "spacer", "name": "Spacer", "category": "layout", "desc": "여백 제어"},
        {"id": "divider", "name": "Divider", "category": "layout", "desc": "구분선 표시"},
        {
            "id": "hero", "name": "HeroBlock", "category": "template", "desc": "최상단 핵심 소개 영역",
            "example_value": {"headline": "안녕하세요", "subheadline": "...", "ctaLabel": "...", "ctaLink": "...", "heroImage": "https://..."}
        },
        {
            "id": "profile", "name": "ProfileBlock", "category": "template", "desc": "이름/직무/자기소개 입력 영역",
            "example_value": {"name": "홍길동", "role": "Frontend Developer", "intro": "...", "profileImage": "...", "links": [{"label": "GitHub", "url": "https://...", "target": "_blank"}]}
        },
        {
            "id": "project", "name": "ProjectBlock", "category": "template", "desc": "프로젝트 정보 입력 영역",
            "example_value": {"title": "...", "summary": "...", "role": "...", "period": {"start": "2024-01", "end": "2024-05", "isCurrent": False}, "techStack": ["React", "TypeScript"], "links": [], "thumbnail": "https://..."}
        },
        {
            "id": "skills", "name": "SkillsBlock", "category": "template", "desc": "기술 스택 입력 영역",
            "example_value": {"category": "Frontend", "items": ["React", "TypeScript", "TailwindCSS"]}
        },
        {
            "id": "experience", "name": "ExperienceBlock", "category": "template", "desc": "경력/활동/인턴 경험 입력 영역",
            "example_value": {"organization": "카카오", "role": "인턴", "period": {"start": "2024-01", "end": "2024-06", "isCurrent": False}, "description": "...", "achievements": ["MAU 10% 개선"]}
        },
        {
            "id": "contact", "name": "ContactBlock", "category": "template", "desc": "연락처 및 외부 링크",
            "example_value": {"email": "hong@gmail.com", "github": {"label": "GitHub", "url": "...", "target": "_blank"}, "blog": {"label": "Blog", "url": "...", "target": "_blank"}, "notion": None}
        },
        {"id": "text", "name": "TextBlock", "category": "template", "desc": "자유 서술용 설명 영역"},
        {"id": "image", "name": "ImageBlock", "category": "template", "desc": "대표 이미지/배너"}
    ]
}

# Tool 1. get_components
@mcp.tool()
def get_components(job_type: str) -> str:
    """
    포트폴리오에 사용할 수 있는 진짜 컴포넌트 목록과 데이터(value) 작성 규칙을 반환
    """
    # 직무에 상관없이 공통 블록 명세서를 제공하여 AI가 규칙을 학습하게 합니다.
    return json.dumps(COMPONENTS_DB["common"], ensure_ascii=False, indent=2)

# Tool 2. validate_layout
@mcp.tool()
def validate_layout(layout_data: Dict[str, Any]) -> str:
    """
    AI가 생성한 레이아웃 구조(JSON)가 규칙에 맞는지 검증
    """
    try:
        errors = []
        valid_ids = [comp["id"] for comp in COMPONENTS_DB["common"]]
        
        # 1. 검사할 블록들을 모두 긁어모읍니다.
        blocks_to_check = []
        
        # Case A: 전체 데이터가 통으로 들어왔을 때
        if "portfolioTemplate" in layout_data:
            blocks_to_check.extend(layout_data["portfolioTemplate"].get("blocks", []))
            if "portfolioContent" in layout_data:
                blocks_to_check.extend(layout_data["portfolioContent"].get("values", []))
                
        # Case B: 클로드가 'blocks' 배열만 잘라서 보냈을 때
        elif "blocks" in layout_data:
            blocks_to_check.extend(layout_data["blocks"])
            
        # Case C: 클로드가 단일 블록(객체) 하나만 보냈을 때
        elif "type" in layout_data:
            blocks_to_check.append(layout_data)
            
        if not blocks_to_check:
            return json.dumps({
                "is_valid": False, 
                "errors": ["검사할 블록 데이터(type)를 찾을 수 없습니다. 형식을 확인해주세요."]
            }, ensure_ascii=False)
            
        # 2. 긁어모은 블록들의 type 이름표가 명세서에 있는지 검사합니다.
        for block in blocks_to_check:
            if not isinstance(block, dict): continue
            block_type = block.get("type")
            
            if not block_type:
                errors.append(f"오류: type이 누락된 블록이 있습니다. (ID: {block.get('blockId', '알수없음')})")
            elif block_type not in valid_ids:
                errors.append(f"오류: 허용되지 않는 블록 type('{block_type}')이 있습니다. (허용: {valid_ids})")
                
        # 3. 결과 반환
        if errors:
            return json.dumps({
                "is_valid": False, 
                "errors": errors, 
                "suggestion": "에러를 확인하고, 반드시 get_components의 type 이름표를 지켜주세요."
            }, ensure_ascii=False)
            
        return json.dumps({"is_valid": True, "message": "해당 파트 검증 완벽 통과! 계속 진행하세요."}, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"is_valid": False, "errors": [f"서버 에러: {str(e)}"]}, ensure_ascii=False)
    


# Tool 3. export_portfolio
@mcp.tool()
def export_portfolio(content: str, file_name: str = "my_portfolio.md") -> str:
    """
    AI가 작성한 포트폴리오 내용(마크다운)을 사용자의 PC 바탕화면에 파일로 저장
    """
    try:
        home = os.path.expanduser("~")
        possible_paths = [
            os.path.join(home, "OneDrive", "바탕 화면"),
            os.path.join(home, "OneDrive", "Desktop"),
            os.path.join(home, "바탕 화면"),
            os.path.join(home, "Desktop")
        ]
        
        desktop_path = next((p for p in possible_paths if os.path.exists(p)), home)
        save_path = os.path.join(desktop_path, file_name)
        
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return json.dumps({
            "is_success": True, 
            "message": f"바탕화면에 '{file_name}' 파일이 성공적으로 저장되었습니다! (경로: {save_path})"
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"is_success": False, "error": f"저장 실패: {str(e)}"}, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run()