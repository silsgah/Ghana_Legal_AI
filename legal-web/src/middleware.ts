import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';

// Only chat and billing routes require authentication
// The landing page (/) and sign-in/sign-up pages are public
const isProtectedRoute = createRouteMatcher([
  '/chat(.*)',    // Chat interface requires login
  '/billing(.*)', // Billing pages
]);

export default clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals and all static files
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
};
