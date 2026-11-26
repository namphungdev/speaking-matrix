# Backend API Agent Instructions (`services/api`)

## 1. Scope & Solution Structure
- Project: Speaking Matrix Backend API — .NET 10 ASP.NET Core Web API.
- Solution: `services/api/SpeakingMatrix/SpeakingMatrix.slnx`.
- Projects:
  - `SpeakingMatrix.Api` (`Microsoft.NET.Sdk.Web`) — entry point `Program.cs`, controllers, Swagger/OpenAPI, `appsettings.json`, `appsettings.Development.json`, `launchSettings.json`.
  - `SpeakingMatrix.Domain` (`Microsoft.NET.Sdk`) — domain layer.
  - `SpeakingMatrix.Application` (`Microsoft.NET.Sdk`) — application layer.
  - `SpeakingMatrix.Infrastructure` (`Microsoft.NET.Sdk`) — infrastructure layer.

## 2. Verified Technology & Commands
- Target framework: `net10.0`; `ImplicitUsings: enable`; `Nullable: enable`.
- Stack: ASP.NET Core Web API, Swashbuckle.AspNetCore 10.3.1, Microsoft.AspNetCore.OpenApi 10.0.13.
- Commands (run in `services/api/SpeakingMatrix`): `dotnet build`, `dotnet run` (or `dotnet run --project SpeakingMatrix.Api`).

## 3. Application Configuration (`Program.cs`)
- `WebApplication.CreateBuilder(args)`; `AddControllers()`; `AddOpenApi()`; `AddEndpointsApiExplorer()`.
- `AddSwaggerGen()` with SwaggerDoc "v1" ("SpeakingMatrix API v1").
- Dev-only: `MapOpenApi()`, `UseSwagger()`, `UseSwaggerUI()` at `/swagger/v1/swagger.json`.
- Middleware: `UseHttpsRedirection()`, `UseAuthorization()`, `MapControllers()`, `app.Run()`.

## 4. Architecture & Dependency Boundaries
- Layered separation: Api (controllers, middleware, Swagger), Domain, Application, Infrastructure.
- Frontend (`apps/web`) and backend are independent apps. Never cross-import files directly between them without a shared package.
- API contract with frontend is not yet defined; do not invent endpoints or data contracts.

## 5. Persistence & Data Storage
- Backend sử dụng SQL Server và Entity Framework Core Code First với Migrations.
- Khi thực hiện công việc liên quan đến persistence, tuân thủ `services/api/docs/architecture/persistence.md`.
- Không tự ý đổi database provider hoặc áp dụng migration lên production.

## 6. Security & Data Boundaries
- Do not commit secrets, API keys, or environment variables.
- `UseHttpsRedirection()` and `UseAuthorization()` are configured; actual auth policy/implementation is not yet defined.

## 7. Architecture Document Review
- Trước khi lập plan hoặc sửa code backend, AI phải đọc tài liệu kiến trúc liên quan trong `services/api/docs/architecture/` (ví dụ `persistence.md`) để nắm các quy tắc và quyết định đã chốt.

## 8. Verification Expectations
- `dotnet build` inside `services/api/SpeakingMatrix` must pass with 0 errors before reporting completion.
- Do not claim verification unless the command was actually run successfully.
