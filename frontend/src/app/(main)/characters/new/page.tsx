"use client";

import { useRouter } from "next/navigation";

import { CharacterForm, type CharacterFormValues } from "@/components/character/character-form";
import { useCreateCharacter } from "@/hooks/use-characters";

export default function NewCharacterPage() {
  const router = useRouter();
  const create = useCreateCharacter();

  async function onSubmit(v: CharacterFormValues) {
    await create.mutateAsync(v);
    router.push("/characters");
  }

  return <CharacterForm submitting={create.isPending} onSubmit={onSubmit} />;
}
