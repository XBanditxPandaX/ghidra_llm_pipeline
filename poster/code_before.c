void* FUN_00401000(
  int param_1,
  int param_2)
{
  void *v;
  v = malloc(param_2);
  if (v != (void*)0x0)
    memcpy(v, param_1, param_2);
  return v;
}
