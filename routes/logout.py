# routes/logout.py
from flask import Blueprint, jsonify, make_response

logout_bp = Blueprint('logout', __name__)

@logout_bp.route('/api/auth/logout', methods=['POST', 'OPTIONS'])
def logout():
    # 1. إنشاء استجابة JSON
    response = make_response(jsonify({
        "success": True, 
        "message": "Logged out successfully",
        "action": "clear_client_storage"
    }))

    # 2. مسح ملفات تعريف الارتباط (Cookies) من المتصفح
    # نضع قيم فارغة وتاريخ انتهاء في الماضي
    response.set_cookie('session', '', expires=0, httponly=True, samesite='Lax')
    response.set_cookie('remember_token', '', expires=0)
    
    # 3. إضافة رؤوس أمان لمنع التخزين المؤقت لبيانات الحساب بعد الخروج
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response, 200