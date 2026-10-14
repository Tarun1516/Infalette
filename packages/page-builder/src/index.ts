/**
 * @infalette/page-builder - Drag-and-drop page builder for Infalette storefronts.
 */

// Block types
export type BlockType =
  | "hero"
  | "product-grid"
  | "product-carousel"
  | "collection-grid"
  | "category_grid"
  | "featured_products"
  | "influencer_story"
  | "faq"
  | "bundles"
  | "text"
  | "image"
  | "video"
  | "spacer"
  | "divider"
  | "cta"
  | "testimonial"
  | "instagram-feed"
  | "newsletter"
  | "footer";

// Block schema
export interface PageBlockSchema {
  id: string;
  type: BlockType;
  props: Record<string, any>;
  children?: PageBlockSchema[];
}

export interface PageSchema {
  id: string;
  title: string;
  slug: string;
  blocks: PageBlockSchema[];
  meta: {
    title?: string;
    description?: string;
    ogImage?: string;
  };
}

// Block definitions
export interface BlockDefinition {
  type: BlockType;
  name: string;
  description: string;
  defaultProps: Record<string, any>;
  propsSchema: PropSchema[];
}

export interface PropSchema {
  name: string;
  label: string;
  type: "text" | "textarea" | "number" | "boolean" | "select" | "image" | "color" | "url";
  required?: boolean;
  default?: any;
  options?: { label: string; value: string }[];
}

// Block definitions registry
export const blockDefinitions: Record<BlockType, BlockDefinition> = {
  hero: {
    type: "hero",
    name: "Hero Section",
    description: "Large hero section with image, title, and CTA",
    defaultProps: {
      title: "Welcome to our store",
      subtitle: "Discover amazing products",
      backgroundImage: "",
      ctaText: "Shop Now",
      ctaLink: "/products",
      alignment: "center",
    },
    propsSchema: [
      { name: "title", label: "Title", type: "text", required: true },
      { name: "subtitle", label: "Subtitle", type: "textarea" },
      { name: "backgroundImage", label: "Background Image", type: "image" },
      { name: "ctaText", label: "CTA Text", type: "text" },
      { name: "ctaLink", label: "CTA Link", type: "url" },
      { name: "alignment", label: "Alignment", type: "select", options: [
        { label: "Left", value: "left" },
        { label: "Center", value: "center" },
        { label: "Right", value: "right" },
      ]},
    ],
  },
  "product-grid": {
    type: "product-grid",
    name: "Product Grid",
    description: "Grid of products",
    defaultProps: {
      title: "Featured Products",
      columns: 4,
      limit: 8,
      collectionId: "",
    },
    propsSchema: [
      { name: "title", label: "Title", type: "text" },
      { name: "columns", label: "Columns", type: "number", default: 4 },
      { name: "limit", label: "Product Limit", type: "number", default: 8 },
      { name: "collectionId", label: "Collection", type: "select" },
    ],
  },
  "product-carousel": {
    type: "product-carousel",
    name: "Product Carousel",
    description: "Scrollable product carousel",
    defaultProps: {
      title: "Trending Now",
      limit: 10,
      autoPlay: true,
    },
    propsSchema: [
      { name: "title", label: "Title", type: "text" },
      { name: "limit", label: "Product Limit", type: "number", default: 10 },
      { name: "autoPlay", label: "Auto Play", type: "boolean", default: true },
    ],
  },
  "collection-grid": {
    type: "collection-grid",
    name: "Collection Grid",
    description: "Grid of collections",
    defaultProps: {
      title: "Shop by Collection",
      columns: 3,
    },
    propsSchema: [
      { name: "title", label: "Title", type: "text" },
      { name: "columns", label: "Columns", type: "number", default: 3 },
    ],
  },
  text: {
    type: "text",
    name: "Text Block",
    description: "Rich text content",
    defaultProps: {
      content: "Enter your text here...",
      alignment: "left",
    },
    propsSchema: [
      { name: "content", label: "Content", type: "textarea", required: true },
      { name: "alignment", label: "Alignment", type: "select", options: [
        { label: "Left", value: "left" },
        { label: "Center", value: "center" },
        { label: "Right", value: "right" },
      ]},
    ],
  },
  image: {
    type: "image",
    name: "Image",
    description: "Single image block",
    defaultProps: {
      src: "",
      alt: "",
      width: "full",
    },
    propsSchema: [
      { name: "src", label: "Image URL", type: "image", required: true },
      { name: "alt", label: "Alt Text", type: "text" },
      { name: "width", label: "Width", type: "select", options: [
        { label: "Full", value: "full" },
        { label: "Half", value: "half" },
        { label: "Third", value: "third" },
      ]},
    ],
  },
  video: {
    type: "video",
    name: "Video",
    description: "Embedded video block",
    defaultProps: {
      url: "",
      autoplay: false,
      controls: true,
    },
    propsSchema: [
      { name: "url", label: "Video URL", type: "url", required: true },
      { name: "autoplay", label: "Autoplay", type: "boolean" },
      { name: "controls", label: "Show Controls", type: "boolean", default: true },
    ],
  },
  spacer: {
    type: "spacer",
    name: "Spacer",
    description: "Empty space block",
    defaultProps: {
      height: 40,
    },
    propsSchema: [
      { name: "height", label: "Height (px)", type: "number", default: 40 },
    ],
  },
  divider: {
    type: "divider",
    name: "Divider",
    description: "Horizontal divider line",
    defaultProps: {
      color: "#e5e7eb",
    },
    propsSchema: [
      { name: "color", label: "Color", type: "color", default: "#e5e7eb" },
    ],
  },
  cta: {
    type: "cta",
    name: "Call to Action",
    description: "CTA button with text",
    defaultProps: {
      text: "Shop Now",
      link: "/products",
      style: "primary",
    },
    propsSchema: [
      { name: "text", label: "Button Text", type: "text", required: true },
      { name: "link", label: "Link", type: "url", required: true },
      { name: "style", label: "Style", type: "select", options: [
        { label: "Primary", value: "primary" },
        { label: "Secondary", value: "secondary" },
        { label: "Outline", value: "outline" },
      ]},
    ],
  },
  testimonial: {
    type: "testimonial",
    name: "Testimonial",
    description: "Customer testimonial block",
    defaultProps: {
      quote: "Amazing products and fast delivery!",
      author: "Happy Customer",
      rating: 5,
    },
    propsSchema: [
      { name: "quote", label: "Quote", type: "textarea", required: true },
      { name: "author", label: "Author", type: "text", required: true },
      { name: "rating", label: "Rating (1-5)", type: "number", default: 5 },
    ],
  },
  "instagram-feed": {
    type: "instagram-feed",
    name: "Instagram Feed",
    description: "Live Instagram feed",
    defaultProps: {
      title: "Follow us on Instagram",
      limit: 6,
    },
    propsSchema: [
      { name: "title", label: "Title", type: "text" },
      { name: "limit", label: "Post Limit", type: "number", default: 6 },
    ],
  },
  newsletter: {
    type: "newsletter",
    name: "Newsletter Signup",
    description: "Email newsletter signup form",
    defaultProps: {
      title: "Subscribe to our newsletter",
      subtitle: "Get updates on new products and offers",
      placeholder: "Enter your email",
      buttonText: "Subscribe",
    },
    propsSchema: [
      { name: "title", label: "Title", type: "text" },
      { name: "subtitle", label: "Subtitle", type: "text" },
      { name: "placeholder", label: "Input Placeholder", type: "text" },
      { name: "buttonText", label: "Button Text", type: "text" },
    ],
  },
  footer: {
    type: "footer",
    name: "Footer",
    description: "Store footer with links",
    defaultProps: {
      showSocialLinks: true,
      showPaymentIcons: true,
    },
    propsSchema: [
      { name: "showSocialLinks", label: "Show Social Links", type: "boolean", default: true },
      { name: "showPaymentIcons", label: "Show Payment Icons", type: "boolean", default: true },
    ],
  },
};

// Block validators
export function validateBlock(block: PageBlockSchema): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  const definition = blockDefinitions[block.type];

  if (!definition) {
    errors.push(`Unknown block type: ${block.type}`);
    return { valid: false, errors };
  }

  for (const propSchema of definition.propsSchema) {
    if (propSchema.required && !block.props[propSchema.name]) {
      errors.push(`Missing required prop: ${propSchema.name}`);
    }
  }

  return { valid: errors.length === 0, errors };
}

export function validatePage(page: PageSchema): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!page.title) {
    errors.push("Page title is required");
  }

  if (!page.slug) {
    errors.push("Page slug is required");
  }

  for (const block of page.blocks) {
    const result = validateBlock(block);
    if (!result.valid) {
      errors.push(`Block ${block.id}: ${result.errors.join(", ")}`);
    }
  }

  return { valid: errors.length === 0, errors };
}

// Block factory
export function createBlock(type: BlockType, props?: Record<string, any>): PageBlockSchema {
  const definition = blockDefinitions[type];
  if (!definition) {
    throw new Error(`Unknown block type: ${type}`);
  }

  return {
    id: generateBlockId(),
    type,
    props: { ...definition.defaultProps, ...props },
  };
}

export function generateBlockId(): string {
  return `block_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Page factory
export function createPage(title: string, slug: string): PageSchema {
  return {
    id: `page_${Date.now()}`,
    title,
    slug,
    blocks: [],
    meta: {},
  };
}

// Get available block types
export function getAvailableBlocks(): BlockDefinition[] {
  return Object.values(blockDefinitions);
}