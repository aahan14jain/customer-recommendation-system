import type { ImgHTMLAttributes } from 'react'

type Src = ImgHTMLAttributes<HTMLImageElement>['src']

type NextImageProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> & {
  src?: Src | { src: string }
}

/**
 * Test double for `next/image` — renders a plain <img> so Jest does not need the image optimizer.
 */
export default function Image({ src, alt = '', ...rest }: NextImageProps) {
  const resolvedSrc =
    typeof src === 'object' && src !== null && 'src' in src
      ? (src as { src: string }).src
      : src

  return <img src={resolvedSrc} alt={alt} {...rest} />
}
