import { useEffect } from "react";
import { socket } from "@/lib/socket";

export function useTaskDue(onDue: (payload: any) => void) {
  useEffect(() => {
    socket.on("task:due", onDue);
    return () => socket.off("task:due", onDue);
  }, [onDue]);
}