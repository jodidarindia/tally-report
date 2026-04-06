import React, { useState } from 'react';
import axios from 'axios';
import { Mail, Lock, Loader } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Login = ({ onLoginSuccess }) => {
  const [step, setStep] = useState('email'); // 'email' or 'otp'
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSendOTP = async (e) => {
    e.preventDefault();
    if (!email || !email.includes('@')) {
      toast.error('Please enter a valid email');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/send-otp`, { email });
      
      if (response.data?.success) {
        toast.success('OTP sent to your email!');
        setStep('otp');
      } else {
        toast.error(response.data?.error || 'Failed to send OTP');
      }
    } catch (error) {
      console.error('Error sending OTP:', error);
      toast.error('Failed to send OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e) => {
    e.preventDefault();
    if (!otp || otp.length !== 6) {
      toast.error('Please enter a 6-digit OTP');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/verify-otp`, { email, otp });
      
      if (response.data?.success) {
        const sessionToken = response.data.data.session_token;
        localStorage.setItem('session_token', sessionToken);
        localStorage.setItem('user_email', email);
        
        toast.success('Login successful!');
        onLoginSuccess(email, sessionToken);
      } else {
        toast.error(response.data?.error || 'Invalid OTP');
      }
    } catch (error) {
      console.error('Error verifying OTP:', error);
      toast.error('Invalid OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-[#064E3B] rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Lock className="text-white" size={32} />
          </div>
          <h1 className="text-3xl font-light text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Tally Reports
          </h1>
          <p className="text-stone-600 mt-2">Secure login with email OTP</p>
        </div>

        {/* Login Form */}
        <div className="bg-white border border-stone-200 rounded-xl p-8 shadow-lg">
          {step === 'email' ? (
            <form onSubmit={handleSendOTP}>
              <div className="mb-6">
                <label className="block text-sm font-medium text-stone-700 mb-2">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 text-stone-400" size={20} />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                    className="w-full pl-11 pr-4 py-3 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#064E3B] focus:border-transparent"
                    disabled={loading}
                    data-testid="email-input"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full btn-primary py-3 flex items-center justify-center gap-2 disabled:opacity-50"
                data-testid="send-otp-button"
              >
                {loading ? (
                  <>
                    <Loader className="animate-spin" size={20} />
                    Sending OTP...
                  </>
                ) : (
                  'Send OTP'
                )}
              </button>

              <p className="text-xs text-stone-500 mt-4 text-center">
                A 6-digit OTP will be sent to your email. Valid for 10 minutes.
              </p>
            </form>
          ) : (
            <form onSubmit={handleVerifyOTP}>
              <div className="mb-6">
                <label className="block text-sm font-medium text-stone-700 mb-2">
                  Enter OTP
                </label>
                <p className="text-xs text-stone-500 mb-3">
                  OTP sent to {email}
                </p>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  className="w-full px-4 py-3 border border-stone-200 rounded-lg text-center text-2xl font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-[#064E3B] focus:border-transparent"
                  disabled={loading}
                  data-testid="otp-input"
                  maxLength={6}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="w-full btn-primary py-3 flex items-center justify-center gap-2 disabled:opacity-50"
                data-testid="verify-otp-button"
              >
                {loading ? (
                  <>
                    <Loader className="animate-spin" size={20} />
                    Verifying...
                  </>
                ) : (
                  'Verify & Login'
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setStep('email');
                  setOtp('');
                }}
                className="w-full mt-3 text-sm text-stone-600 hover:text-stone-900"
              >
                ← Change email
              </button>

              <p className="text-xs text-stone-500 mt-4 text-center">
                Didn't receive OTP?{' '}
                <button
                  type="button"
                  onClick={handleSendOTP}
                  className="text-[#064E3B] font-medium hover:underline"
                  disabled={loading}
                >
                  Resend
                </button>
              </p>
            </form>
          )}
        </div>

        <p className="text-xs text-stone-500 mt-6 text-center">
          🔒 Secure authentication via email OTP
        </p>
      </div>
    </div>
  );
};

export default Login;
