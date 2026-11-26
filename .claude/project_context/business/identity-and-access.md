# Identity & Access — Business Context

- Users are ASP.NET Identity users (`ApplicationUser : IdentityUser`) with
  roles; email must be unique (`Infrastructure/DependencyInjection.cs`).
- The API authenticates with JWT bearer tokens validated for issuer, audience,
  signing key and lifetime (`Api/Program.cs`).
- No login/registration endpoint or token issuing exists yet; the web app has
  no authentication.
