"use client";

import { useParams, useRouter } from "next/navigation";

import { CharacterForm, type CharacterFormValues } from "@/components/character/character-form";
import { Spinner } from "@/components/ui/states";
import { useCharacter, useUpdateCharacter } from "@/hooks/use-characters";

export default function EditCharacterPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { data, isPending } = useCharacter(params.id);
  const update = useUpdateCharacter(params.id);

  async function onSubmit(v: CharacterFormValues) {
    await update.mutateAsync(v);
    router.push("/characters");
  }

  if (isPending || !data) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  return <CharacterForm initial={data} submitting={update.isPending} onSubmit={onSubmit} />;
}
