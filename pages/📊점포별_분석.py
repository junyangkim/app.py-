from datetime import datetime
import io
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# 🗂️ 메인페이지에서 데이터 가져오기 
# =========================================================

# 공용 냉장고에서 통째로 데이터 끌고 오기
if "all_data" in st.session_state:
    db = st.session_state["all_data"]
    
    # 2. 이제 여기서 필요한 시트를 변수로 쏙쏙 뽑아서 편하게 요리하세요!
    c1_df = db["c1"]
    c2_df = db["c2"]
    c3_df = db["c3"]
    c4_df = db["c4"]
    c5_df = db["c5"]    