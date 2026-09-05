"""
Autonomous Action Dispatcher.
Constructs dynamic intervention payloads for checkout gateways.
"""
import secrets


class AutoResponder:
    @staticmethod
    def dispatch_action(action: str, order_id: str, phone: str, order_value_inr: float) -> dict:
        """
        Generates downstream execution instructions based on risk classification.
        """
        if action == "ALLOW_COD":
            return {
                "status": "APPROVED",
                "message": "Order approved for instant 1-click Cash on Delivery.",
                "step_up_required": False
            }

        elif action == "VERIFY_STEP_UP_OTP":
            # Cryptographically generated 6-digit challenge (server-side only).
            otp_token = f"{secrets.randbelow(900000) + 100000}"
            return {
                "status": "CHALLENGE_REQUIRED",
                "message": f"Verification code dispatched to +91******{str(phone)[-4:]}",
                "step_up_required": True,
                "challenge_type": "WHATSAPP_OTP",
                "masked_phone": f"{phone[:3]}******{phone[-4:]}",
                "mock_otp_token": otp_token,
                "advance_deposit_option_inr": 49.0
            }

        elif action == "RESTRICT_PREPAID_ONLY":
            prepay_discount_inr = round(min(150.0, order_value_inr * 0.05), 2)
            return {
                "status": "COD_DISABLED",
                "message": "Cash on Delivery disabled due to elevated logistics risk.",
                "step_up_required": False,
                "payment_restriction": "PREPAID_ONLY",
                "incentive_offer": {
                    "discount_applied_inr": prepay_discount_inr,
                    "discount_reason": "5% Instant Discount for UPI/Card Settlement",
                    "final_payable_inr": round(order_value_inr - prepay_discount_inr, 2)
                }
            }

        return {"status": "UNKNOWN_ACTION"}