export default function LoadingSpinner({ size = 6 }) {
  return (
    <div className={`animate-spin rounded-full w-${size} h-${size} border-2 border-border border-t-accent`} />
  )
}
