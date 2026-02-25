import { PrismaClient, Role, SchoolTier, BusinessTier, ProjectStatus } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  await prisma.portfolioArtifact.deleteMany();
  await prisma.projectFeedback.deleteMany();
  await prisma.projectSubmission.deleteMany();
  await prisma.projectApplication.deleteMany();
  await prisma.project.deleteMany();
  await prisma.user.deleteMany();
  await prisma.school.deleteMany();
  await prisma.businessOrg.deleteMany();

  const school = await prisma.school.create({
    data: {
      name: 'Riverside High School',
      domain: 'riverside.edu',
      tier: SchoolTier.CAMPUS,
      seatLimit: 500,
      reportingEnabled: true,
      outcomeInsights: true
    }
  });

  const business = await prisma.businessOrg.create({
    data: {
      name: 'GrowthOps Agency',
      website: 'https://growthops.example.com',
      tier: BusinessTier.GROWTH,
      monthlyPostingLimit: 10,
      priorityAccess: true
    }
  });

  const passwordHash = await bcrypt.hash('Password123!', 10);

  await prisma.user.create({
    data: {
      name: 'Platform Admin',
      email: 'superadmin@skillbridge.app',
      role: Role.SUPER_ADMIN,
      passwordHash
    }
  });

  const schoolAdmin = await prisma.user.create({
    data: {
      name: 'Avery SchoolAdmin',
      email: 'admin@riverside.edu',
      role: Role.SCHOOL_ADMIN,
      schoolId: school.id,
      passwordHash
    }
  });

  await prisma.user.create({
    data: {
      name: 'Bri BusinessAdmin',
      email: 'owner@growthops.example.com',
      role: Role.BUSINESS_ADMIN,
      businessOrgId: business.id,
      passwordHash
    }
  });

  const students = await Promise.all(
    Array.from({ length: 5 }).map((_, idx) =>
      prisma.user.create({
        data: {
          name: `Student ${idx + 1}`,
          email: `student${idx + 1}@riverside.edu`,
          role: Role.STUDENT,
          schoolId: school.id,
          passwordHash
        }
      })
    )
  );

  await prisma.schoolBusinessApproval.create({
    data: { schoolId: school.id, businessOrgId: business.id, approved: true }
  });

  const projectData = [
    {
      title: 'Social Media Growth Campaign',
      description: 'Create a data-driven social campaign for local community outreach.',
      deliverables: 'Campaign calendar, KPI dashboard, retrospective',
      requiredSkills: ['marketing', 'analytics', 'storytelling'],
      expectedHours: 20,
      timeline: '4 weeks',
      category: 'marketing'
    },
    {
      title: 'Website Accessibility Audit',
      description: 'Review and improve accessibility on a public website.',
      deliverables: 'Audit report, prioritized fixes, implementation demo',
      requiredSkills: ['web-dev', 'a11y', 'qa'],
      expectedHours: 30,
      timeline: '6 weeks',
      category: 'web dev'
    },
    {
      title: 'Customer Insights Dashboard',
      description: 'Analyze customer survey data and propose product opportunities.',
      deliverables: 'Clean dataset, dashboard, presentation',
      requiredSkills: ['analytics', 'sql', 'presentation'],
      expectedHours: 25,
      timeline: '5 weeks',
      category: 'analytics'
    }
  ];

  for (const [idx, project] of projectData.entries()) {
    const createdProject = await prisma.project.create({
      data: {
        ...project,
        status: idx === 0 ? ProjectStatus.OPEN : ProjectStatus.DRAFT,
        schoolId: school.id,
        businessOrgId: business.id
      }
    });

    if (idx === 0) {
      await prisma.projectApplication.create({
        data: {
          projectId: createdProject.id,
          studentId: students[0].id,
          status: 'ACCEPTED',
          note: 'Excited to build measurable outcomes.'
        }
      });
    }
  }

  console.log('Seed complete.\nLogin users password: Password123!');
  console.log(`School admin: ${schoolAdmin.email}`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
