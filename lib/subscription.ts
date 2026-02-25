import { BusinessTier, SchoolTier } from '@prisma/client';

export function schoolTierDefaults(tier: SchoolTier) {
  switch (tier) {
    case SchoolTier.PILOT:
      return { seatLimit: 100, reportingEnabled: false, outcomeInsights: false };
    case SchoolTier.CAMPUS:
      return { seatLimit: 500, reportingEnabled: true, outcomeInsights: true };
    case SchoolTier.ENTERPRISE:
      return { seatLimit: 5000, reportingEnabled: true, outcomeInsights: true };
  }
}

export function businessTierDefaults(tier: BusinessTier) {
  switch (tier) {
    case BusinessTier.STARTER:
      return { monthlyPostingLimit: 3, priorityAccess: false };
    case BusinessTier.GROWTH:
      return { monthlyPostingLimit: 10, priorityAccess: false };
    case BusinessTier.PARTNER:
      return { monthlyPostingLimit: 100, priorityAccess: true };
  }
}
