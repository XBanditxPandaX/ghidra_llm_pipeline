/* Allocates a buffer and copies src.
 * @param src   source data pointer
 * @param size  number of bytes       */
void* copy_and_allocate(
  void*  src,
  size_t size)
{
  void* d = malloc(size);
  if (d) memcpy(d, src, size);
  return d;
}
