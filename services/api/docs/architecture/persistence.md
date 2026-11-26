# Persistence Architecture (`services/api`)

## 1. Quyết định đã chốt
- Database: SQL Server.
- ORM: Entity Framework Core.
- Quản lý schema: Code First với EF Core Migrations.

## 2. Ràng buộc và quy định
- `DbContext`, cấu hình EF Core và migrations thuộc lớp Infrastructure, trừ khi kiến trúc hiện tại có quyết định khác đã được ghi nhận.
- Connection string lấy từ configuration (`appsettings.json` hoặc biến môi trường); không commit credentials hoặc secrets vào repository.
- Migrations phải được review và lưu trong source control.
- Không tự ý đổi database provider hoặc áp dụng migration lên production.

## 3. Phạm vi chưa quy định
- Chưa quy định database schema, naming convention, phiên bản package EF Core, hay quy trình deployment. Những quyết định này sẽ được bổ sung khi có căn cứ.
