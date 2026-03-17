import express from "express";
import nodemailer from "nodemailer";
import cors from "cors";
import crypto from "crypto";

const app = express();
app.use(cors());
app.use(express.json());

// ================================
// تخزين OTP
// ================================
const otpStore = new Map();

// ================================
// إعداد Gmail
// ================================
const transporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    user: "ip8a2024@gmail.com",
    pass: "lfyr mkds gioy ltlu"
  }
});

// ================================
// دوال مساعدة
// ================================
function generateOTP() {
  return Math.floor(100000 + Math.random() * 900000).toString(); // 6 أرقام
}

function hashOTP(otp) {
  return crypto.createHash("sha256").update(otp).digest("hex");
}

// ================================
// تنظيف OTP المنتهي
// ================================
setInterval(() => {
  const now = Date.now();
  for (let [email, data] of otpStore) {
    if (now > data.exp) {
      otpStore.delete(email);
    }
  }
}, 60000); // كل دقيقة

// ================================
// إرسال OTP
// ================================
app.post("/send-otp", async (req, res) => {
  const { email } = req.body;

  if (!email || !email.includes("@")) {
    return res.status(400).json({ error: "Invalid email" });
  }

  const otp = generateOTP();

  otpStore.set(email, {
    otp: hashOTP(otp),
    exp: Date.now() + 5 * 60 * 1000 // 5 دقائق
  });

  try {
    await transporter.sendMail({
      from: "ip8a2024@gmail.com",
      to: email,
      subject: "Your OTP Code",
      html: `<h2>Your OTP is: ${otp}</h2>`
    });

    console.log(`OTP sent to ${email}`);
    res.json({ success: true });

  } catch (err) {
    console.error("Email error:", err);
    res.status(500).json({ error: "Failed to send OTP" });
  }
});

// ================================
// التحقق من OTP
// ================================
app.post("/verify-otp", (req, res) => {
  const { email, otp } = req.body;
  const data = otpStore.get(email);

  if (!data) {
    return res.status(400).json({ error: "No OTP" });
  }

  if (Date.now() > data.exp) {
    otpStore.delete(email);
    return res.status(400).json({ error: "Expired" });
  }

  if (data.otp !== hashOTP(otp)) {
    return res.status(400).json({ error: "Wrong OTP" });
  }

  otpStore.delete(email);
  res.json({ success: true });
});

// ================================
app.listen(3000, () => console.log("Server running on port 3000"));
