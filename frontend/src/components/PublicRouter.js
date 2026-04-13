import React from 'react';
import LandingPage from '../pages/LandingPage';
import SignupPage from '../pages/SignupPage';
import LoginPage from './LoginPage';
import { PrivacyPolicy, TermsOfService, RefundPolicy, ContactPage, SocialMediaPage } from '../pages/PublicPages';

const PublicRouter = ({ view, onNavigate, onLogin, loginLoading }) => {
  const back = () => onNavigate('landing');

  switch (view) {
    case 'signup':
      return <SignupPage onNavigateToLogin={() => onNavigate('login')} onNavigateToLanding={back} />;
    case 'privacy':
      return <PrivacyPolicy onNavigate={onNavigate} onBack={back} />;
    case 'terms':
      return <TermsOfService onNavigate={onNavigate} onBack={back} />;
    case 'refund':
      return <RefundPolicy onNavigate={onNavigate} onBack={back} />;
    case 'contact':
      return <ContactPage onNavigate={onNavigate} onBack={back} />;
    case 'social':
      return <SocialMediaPage onNavigate={onNavigate} onBack={back} />;
    case 'login':
      return <LoginPage onLogin={onLogin} loading={loginLoading} onNavigate={onNavigate} />;
    default:
      return (
        <LandingPage
          onNavigateToLogin={() => onNavigate('login')}
          onNavigateToSignup={() => onNavigate('signup')}
          onNavigate={onNavigate}
        />
      );
  }
};

export default PublicRouter;
