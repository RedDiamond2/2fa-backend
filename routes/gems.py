# routes/gems.py
from flask import Blueprint, request, jsonify
from services.gem_service import GemService
from middleware.auth_guard import token_required # نفترض وجود هذا الميدل وير للحماية

gems_bp = Blueprint('gems', __name__)

@gems_bp.route('/status', methods=['GET'])
@token_required
def get_gems_status(current_user_email):
    """جلب رصيد الجواهر وسجل العمليات"""
    stats = GemService.get_user_stats(current_user_email)
    if not stats:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify(stats), 200

@gems_bp.route('/claim-reward', methods=['POST'])
@token_required
def claim_profile_reward(current_user_email):
    """طلب مكافأة إكمال معلومة (عمر، جنس، إلخ)"""
    data = request.json
    field = data.get('field') # مثلاً 'age' أو 'gender'

    if not field:
        return jsonify({"error": "Field is required"}), 400

    success, message = GemService.handle_profile_reward(current_user_email, field)
    
    if success:
        return jsonify({"msg": message, "added": 20}), 200
    else:
        return jsonify({"error": message}), 400

@gems_bp.route('/referral-info', methods=['GET'])
@token_required
def get_referral_info(current_user_email):
    """جلب كود الإحالة الخاص بالمستخدم"""
    stats = GemService.get_user_stats(current_user_email)
    ref_code = stats['referral_code']
    
    # بناء الرابط الخاص بالمستخدم (رابط الـ Frontend)
    ref_link = f"https://RedDiamond2.github.io/index.html?ref={ref_code}"
    
    return jsonify({
        "ref_code": ref_code,
        "ref_link": ref_link
    }), 200
