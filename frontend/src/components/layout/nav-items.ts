import { BookOpen, Globe, Home, MessageCircle, Settings, User, UserCircle2 } from "lucide-react";

export const PRIMARY_NAV = [
  { href: "/", label: "홈", icon: Home },
  { href: "/characters", label: "캐릭터", icon: User },
  { href: "/worlds", label: "세계관", icon: Globe },
  { href: "/novels", label: "소설", icon: BookOpen },
  { href: "/chats", label: "채팅", icon: MessageCircle },
] as const;

// Mobile bottom tabs keep 4 primary + 더보기 (design 7.2.2).
export const MOBILE_TABS = [
  { href: "/", label: "홈", icon: Home },
  { href: "/characters", label: "캐릭터", icon: User },
  { href: "/novels", label: "소설", icon: BookOpen },
  { href: "/chats", label: "채팅", icon: MessageCircle },
] as const;

export const SECONDARY_NAV = [
  { href: "/worlds", label: "세계관", icon: Globe },
  { href: "/personas", label: "페르소나", icon: UserCircle2 },
  { href: "/settings", label: "설정", icon: Settings },
] as const;
