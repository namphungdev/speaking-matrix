namespace SpeakingMatrix.Infrastructure.Persistence
{
    using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
    using Microsoft.EntityFrameworkCore;
    using SpeakingMatrix.Infrastructure.Identity;

    /// <summary>
    /// Defines the <see cref="ApplicationDbContext" />
    /// </summary>
    public sealed class ApplicationDbContext(
    DbContextOptions<ApplicationDbContext> options)
    : IdentityDbContext<ApplicationUser>(options)
    {
    }
}
