import React from 'react';
import LandingPage from '../pages/LandingPage';
import SignupPage from '../pages/SignupPage';
import LoginPage from './LoginPage';
import QuestionnaireForm from '../pages/QuestionnaireForm';
import BlogListPage from '../pages/BlogPage';
import { ProductPresentationPage, DeploymentGuidePage } from '../pages/ResourcesPages';
import { PrivacyPolicy, TermsOfService, RefundPolicy, ContactPage, SocialMediaPage } from '../pages/PublicPages';

const PublicRouter = ({ view, onNavigate, onLogin, loginLoading }) => {
  const back = () => onNavigate('landing');

  // iter-123: /blog and /blog/:slug deep-links are handled here even
  // though the rest of the app is single-view. Reading location.pathname
  // once at render lets us restore the correct slug on refresh.
  const path = typeof window !== 'undefined' ? window.location.pathname : '';
  const blogSlug = path.startsWith('/blog/') ? path.slice(6) : '';
  const isBlogRoute = view === 'blog' || path === '/blog' || path.startsWith('/blog/');

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
    case 'questionnaire':
      return <QuestionnaireForm onBack={back} />;
    case 'blog':
      return <BlogListPage onNavigate={onNavigate} initialSlug={blogSlug} />;
    case 'product-presentation':
      return <ProductPresentationPage onBack={back} />;
    case 'deployment-guide':
      return <DeploymentGuidePage onBack={back} />;
    case 'login':
      return <LoginPage onLogin={onLogin} loading={loginLoading} onNavigate={onNavigate} />;
    default:
      if (isBlogRoute) {
        return <BlogListPage onNavigate={onNavigate} initialSlug={blogSlug} />;
      }
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
